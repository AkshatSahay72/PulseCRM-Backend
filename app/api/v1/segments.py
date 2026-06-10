from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db
from app.models.segment import Segment
from app.schemas.segment import SegmentCreate, SegmentResponse
from app.schemas.customer import CustomerResponse
from app.services.segment_engine import evaluate_segment_rules
from app.services.ai import ai_service

router = APIRouter()

@router.post("/", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
def create_segment(segment_in: SegmentCreate, db: Session = Depends(get_db)):
    db_segment = Segment(
        name=segment_in.name,
        description=segment_in.description,
        rules=segment_in.rules
    )
    db.add(db_segment)
    db.commit()
    db.refresh(db_segment)
    return db_segment


@router.get("/", response_model=List[SegmentResponse])
def list_segments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Segment).offset(skip).limit(limit).all()


@router.get("/{segment_id}/evaluate", response_model=List[CustomerResponse])
def evaluate_segment(segment_id: int, db: Session = Depends(get_db)):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Segment not found"
        )
    return evaluate_segment_rules(segment.rules, db)


@router.post("/ai-build", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
def create_segment_from_prompt(prompt: str = Query(...), db: Session = Depends(get_db)):
    try:
        data = ai_service.generate_segment_from_prompt(prompt)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    db_segment = Segment(
        name=data["name"],
        description=data["description"],
        rules=data["rules"]
    )
    db.add(db_segment)
    db.commit()
    db.refresh(db_segment)
    return db_segment


@router.get("/{segment_id}/analytics", status_code=status.HTTP_200_OK)
def get_segment_analytics(segment_id: int, db: Session = Depends(get_db)):
    from app.models.campaign import Campaign, CommunicationLog

    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Segment not found"
        )

    campaigns = db.query(Campaign).filter(Campaign.segment_id == segment_id).all()
    campaign_ids = [c.id for c in campaigns]

    if not campaign_ids:
        return {
            "segment_id": segment_id,
            "segment_name": segment.name,
            "metrics": {
                "total_campaigns": 0,
                "total_sent": 0,
                "delivered_count": 0,
                "opened_count": 0,
                "clicked_count": 0,
                "failed_count": 0
            },
            "performance_rates": {
                "delivery_rate_pct": 0.0,
                "open_rate_pct": 0.0,
                "click_rate_pct": 0.0
            }
        }

    total_sent = db.query(CommunicationLog).filter(CommunicationLog.campaign_id.in_(campaign_ids)).count()
    
    delivered_count = db.query(CommunicationLog).filter(
        CommunicationLog.campaign_id.in_(campaign_ids),
        CommunicationLog.status.in_(["delivered", "opened", "clicked"])
    ).count()

    opened_count = db.query(CommunicationLog).filter(
        CommunicationLog.campaign_id.in_(campaign_ids),
        CommunicationLog.status.in_(["opened", "clicked"])
    ).count()

    clicked_count = db.query(CommunicationLog).filter(
        CommunicationLog.campaign_id.in_(campaign_ids),
        CommunicationLog.status == "clicked"
    ).count()

    failed_count = db.query(CommunicationLog).filter(
        CommunicationLog.campaign_id.in_(campaign_ids),
        CommunicationLog.status == "failed"
    ).count()

    delivery_rate = round((delivered_count / total_sent) * 100, 2) if total_sent > 0 else 0.0
    open_rate = round((opened_count / delivered_count) * 100, 2) if delivered_count > 0 else 0.0
    click_rate = round((clicked_count / opened_count) * 100, 2) if opened_count > 0 else 0.0

    return {
        "segment_id": segment_id,
        "segment_name": segment.name,
        "metrics": {
            "total_campaigns": len(campaign_ids),
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


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_segment(segment_id: int, db: Session = Depends(get_db)):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Segment not found"
        )
    db.delete(segment)
    db.commit()
    return None
