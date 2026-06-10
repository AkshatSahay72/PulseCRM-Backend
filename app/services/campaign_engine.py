import logging
import httpx
from typing import List
import os

from app.core.database import SessionLocal
from app.models.customer import Customer
from app.models.order import Order
from app.models.campaign import Campaign, CommunicationLog
from app.services.ai import ai_service

logger = logging.getLogger("uvicorn.error")

CHANNEL_SERVICE_URL = os.getenv("CHANNEL_SERVICE_URL", "http://127.0.0.1:8001/send")

def trigger_outbound_campaign(campaign_id: int, customer_ids: List[int], campaign_topic: str):
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            return
            
        campaign.status = "sending"
        db.commit()

        client = httpx.Client()
        sent_count = 0
        
        for cid in customer_ids:
            customer = db.query(Customer).filter(Customer.id == cid).first()
            if not customer:
                continue
            
            orders = db.query(Order).filter(Order.customer_id == cid).all()
            
            name = f"{customer.first_name} {customer.last_name}"
            msg = ai_service.generate_personalized_message(
                customer_name=name,
                recent_orders=orders,
                campaign_topic=campaign_topic
            )
            
            log = CommunicationLog(
                campaign_id=campaign_id,
                customer_id=cid,
                status="pending"
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            
            channel = "email" if customer.email else "sms"
            recipient = customer.email if customer.email else customer.phone
            
            try:
                response = client.post(CHANNEL_SERVICE_URL, json={
                    "log_id": log.id,
                    "recipient": recipient,
                    "message": msg,
                    "channel": channel
                })
                if response.status_code == 202:
                    sent_count += 1
                else:
                    log.status = "failed"
                    log.error_message = f"Channel error: {response.text}"
                    db.commit()
            except Exception as e:
                log.status = "failed"
                log.error_message = str(e)
                db.commit()
                
        client.close()
        campaign.status = "completed" if sent_count > 0 else "failed"
        db.commit()
        
    except Exception as e:
        logger.error(f"Campaign run error: {e}")
    finally:
        db.close()
