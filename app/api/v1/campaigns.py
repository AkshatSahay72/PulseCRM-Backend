from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import logging

from app.api.deps import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.models.segment import Segment
from app.models.campaign import Campaign, CommunicationLog, CampaignEvent
from app.schemas.campaign import CampaignCreate, CampaignResponse, CallbackPayload
from app.services.ai import ai_service
from app.services.segment_engine import evaluate_segment_rules
from app.services.campaign_engine import trigger_outbound_campaign

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(campaign_in: CampaignCreate, db: Session = Depends(get_db)):
    if campaign_in.segment_id:
        segment = db.query(Segment).filter(Segment.id == campaign_in.segment_id).first()
        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Segment not found"
            )

    campaign = Campaign(
        name=campaign_in.name,
        subject=campaign_in.subject,
        message_template=campaign_in.message_template,
        segment_id=campaign_in.segment_id,
        status="draft"
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/", response_model=List[CampaignResponse])
def list_campaigns(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Campaign).offset(skip).limit(limit).all()


@router.post("/{campaign_id}/send", status_code=status.HTTP_202_ACCEPTED)
def send_campaign(campaign_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
        
    if not campaign.segment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign segment not assigned"
        )

    segment = db.query(Segment).filter(Segment.id == campaign.segment_id).first()
    customers = evaluate_segment_rules(segment.rules, db)
    if not customers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target segment is empty"
        )

    customer_ids = [c.id for c in customers]
    topic = f"Name: {campaign.name}. Subject: {campaign.subject}. Template: {campaign.message_template}"
    
    background_tasks.add_task(
        trigger_outbound_campaign,
        campaign_id,
        customer_ids,
        topic
    )
    
    return {
        "status": "accepted",
        "detail": f"Dispatched campaign to {len(customer_ids)} customers"
    }


@router.post("/callback", status_code=status.HTTP_200_OK)
def campaign_callback(payload: CallbackPayload, db: Session = Depends(get_db)):
    log = db.query(CommunicationLog).filter(CommunicationLog.id == payload.log_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log entry not found"
        )

    # Idempotency check
    existing = db.query(CampaignEvent).filter(
        CampaignEvent.communication_log_id == payload.log_id,
        CampaignEvent.event_type == payload.status
    ).first()
    if existing:
        return {"status": "ignored"}

    current = log.status
    new = payload.status
    
    hierarchy = {"pending": 0, "failed": 0, "delivered": 1, "opened": 2, "clicked": 3}
    
    # Do not downgrade status on slow/delayed webhooks
    if new == "failed" or hierarchy.get(new, 0) > hierarchy.get(current, 0):
        log.status = new
        if new == "failed":
            log.error_message = payload.error_message
        db.commit()

    event = CampaignEvent(
        communication_log_id=payload.log_id,
        event_type=new
    )
    db.add(event)
    db.commit()

    return {"status": "processed", "log_id": payload.log_id, "state": new}


@router.get("/analytics/dashboard", status_code=status.HTTP_200_OK)
def get_global_dashboard_analytics(db: Session = Depends(get_db)):
    total_campaigns = db.query(Campaign).count()
    total_customers = db.query(Customer).count()
    total_sent = db.query(CommunicationLog).count()

    delivered_count = db.query(CommunicationLog).filter(
        CommunicationLog.status.in_(["delivered", "opened", "clicked"])
    ).count()

    opened_count = db.query(CommunicationLog).filter(
        CommunicationLog.status.in_(["opened", "clicked"])
    ).count()

    clicked_count = db.query(CommunicationLog).filter(
        CommunicationLog.status == "clicked"
    ).count()

    failed_count = db.query(CommunicationLog).filter(
        CommunicationLog.status == "failed"
    ).count()

    delivery_rate = round((delivered_count / total_sent) * 100, 2) if total_sent > 0 else 0.0
    open_rate = round((opened_count / delivered_count) * 100, 2) if delivered_count > 0 else 0.0
    click_rate = round((clicked_count / opened_count) * 100, 2) if opened_count > 0 else 0.0

    return {
        "summary": {
            "total_campaigns": total_campaigns,
            "total_customers_registered": total_customers,
            "total_messages_triggered": total_sent
        },
        "aggregate_funnel": {
            "delivered": delivered_count,
            "opened": opened_count,
            "clicked": clicked_count,
            "failed": failed_count
        },
        "performance_rates": {
            "delivery_rate_pct": delivery_rate,
            "open_rate_pct": open_rate,
            "click_rate_pct": click_rate
        }
    }


@router.get("/test-personalize/{customer_id}", status_code=status.HTTP_200_OK)
def test_personalize_message(
    customer_id: int, 
    campaign_topic: str = Query(...),
    db: Session = Depends(get_db)
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    orders = db.query(Order).filter(Order.customer_id == customer_id).all()
    name = f"{customer.first_name} {customer.last_name}"
    msg = ai_service.generate_personalized_message(
        customer_name=name,
        recent_orders=orders,
        campaign_topic=campaign_topic
    )
    return {
        "customer_id": customer.id,
        "customer_name": name,
        "orders_analyzed": len(orders),
        "campaign_topic": campaign_topic,
        "personalized_message": msg
    }


@router.get("/{campaign_id}/analytics", status_code=status.HTTP_200_OK)
def get_campaign_analytics(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    total_sent = db.query(CommunicationLog).filter(CommunicationLog.campaign_id == campaign_id).count()

    delivered_count = db.query(CommunicationLog).filter(
        CommunicationLog.campaign_id == campaign_id,
        CommunicationLog.status.in_(["delivered", "opened", "clicked"])
    ).count()

    opened_count = db.query(CommunicationLog).filter(
        CommunicationLog.campaign_id == campaign_id,
        CommunicationLog.status.in_(["opened", "clicked"])
    ).count()

    clicked_count = db.query(CommunicationLog).filter(
        CommunicationLog.campaign_id == campaign_id,
        CommunicationLog.status == "clicked"
    ).count()

    failed_count = db.query(CommunicationLog).filter(
        CommunicationLog.campaign_id == campaign_id,
        CommunicationLog.status == "failed"
    ).count()

    delivery_rate = round((delivered_count / total_sent) * 100, 2) if total_sent > 0 else 0.0
    open_rate = round((opened_count / delivered_count) * 100, 2) if delivered_count > 0 else 0.0
    click_rate = round((clicked_count / opened_count) * 100, 2) if opened_count > 0 else 0.0

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "campaign_status": campaign.status,
        "metrics": {
            "total_sent": total_sent,
            "delivered_count": delivered_count,
            "opened_count": opened_count,
            "clicked_count": clicked_count,
            "failed_count": failed_count
        },
        "performance_rates": {
            "delivery_rate_pct": delivery_rate,
            "open_rate_pct": open_rate,
            "click_rate_pct": click_rate
        }
    }


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    db.delete(campaign)
    db.commit()
    return None


@router.post("/ai-copilot", status_code=status.HTTP_200_OK)
def campaign_ai_copilot(goal: str = Query(...)):
    try:
        recommendation = ai_service.generate_copilot_recommendation(goal)
        return recommendation
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


