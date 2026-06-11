import logging
import httpx
from typing import List
import os
import random
import time
import threading
from dotenv import load_dotenv

from app.core.database import SessionLocal
from app.models.customer import Customer
from app.models.order import Order
from app.models.campaign import Campaign, CommunicationLog, CampaignEvent
from app.services.ai import ai_service

# Load env variables
load_dotenv()

logger = logging.getLogger("uvicorn.error")

def send_email_via_brevo(recipient_email: str, message_text: str) -> bool:
    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        logger.warning("BREVO_API_KEY not set in environment. Simulating delivery locally.")
        return False

    test_emails = ["akisahay27@gmail.com", "akiisahay18@gmail.com"]
    target_email = recipient_email
    if recipient_email not in test_emails:
        # Default to akisahay27@gmail.com for trial purposes
        target_email = test_emails[0]
        logger.info(f"Trial mode: Redirecting email from {recipient_email} to {target_email}")

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    # Convert plain text to simple HTML (replace newlines with br)
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
            <h2 style="color: #2563eb; margin-top: 0;">PulseCRM Campaign Outbound</h2>
            <p style="font-size: 16px; white-space: pre-wrap;">{message_text}</p>
            <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;">
            <p style="font-size: 12px; color: #888888; margin-bottom: 0;">Sent via PulseCRM Campaign Engine.</p>
        </div>
    </body>
    </html>
    """

    payload = {
        "sender": {
            "name": "PulseCRM Team",
            "email": "akisahay27@gmail.com"
        },
        "to": [
            {
                "email": target_email,
                "name": target_email.split("@")[0]
            }
        ],
        "subject": "Exclusive PulseCRM Campaign Offer",
        "htmlContent": html_content
    }

    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code in [200, 201, 202]:
                logger.info(f"Successfully sent email to {target_email} via Brevo. Status: {response.status_code}")
                return True
            else:
                logger.error(f"Brevo API error: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Error sending email via Brevo: {e}")
        return False

def add_campaign_event(db, log_id: int, event_type: str):
    # Check for duplicate events
    existing = db.query(CampaignEvent).filter(
        CampaignEvent.communication_log_id == log_id,
        CampaignEvent.event_type == event_type
    ).first()
    if not existing:
        event = CampaignEvent(
            communication_log_id=log_id,
            event_type=event_type
        )
        db.add(event)
        db.commit()

def process_delivery_lifecycle(log_id: int, recipient: str, channel: str, message: str):
    db = SessionLocal()
    try:
        # --- PHASE 1: Delivery status ---
        time.sleep(random.uniform(1.0, 2.0))
        
        is_success = False
        api_key = os.getenv("BREVO_API_KEY")
        if channel == "email" and api_key:
            logger.info(f"Log {log_id}: Dispatching email to {recipient} via Brevo API...")
            is_success = send_email_via_brevo(recipient, message)
        else:
            reason = "Channel is not email" if channel != "email" else "BREVO_API_KEY env variable is not set"
            logger.info(f"Log {log_id}: Simulating delivery locally. (Reason: {reason})")
            is_success = random.random() < 0.90
        
        log = db.query(CommunicationLog).filter(CommunicationLog.id == log_id).first()
        if not log:
            return

        if is_success:
            logger.info(f"Log {log_id}: Message delivered to {recipient} via {channel}.")
            log.status = "delivered"
            db.commit()
            add_campaign_event(db, log_id, "delivered")
            
            # --- PHASE 2: Open status ---
            time.sleep(random.uniform(2.0, 4.0))
            is_opened = random.random() < 0.60
            if is_opened:
                logger.info(f"Log {log_id}: Message opened by {recipient}.")
                log.status = "opened"
                db.commit()
                add_campaign_event(db, log_id, "opened")
                
                # --- PHASE 3: Click status ---
                time.sleep(random.uniform(1.0, 3.0))
                is_clicked = random.random() < 0.30
                if is_clicked:
                    logger.info(f"Log {log_id}: Link clicked by {recipient}.")
                    log.status = "clicked"
                    db.commit()
                    add_campaign_event(db, log_id, "clicked")
        else:
            error_reason = "Brevo transmission error" if (channel == "email" and api_key) else random.choice([
                "Invalid recipient address",
                "Inbox capacity exceeded",
                "Carrier routing failure"
            ])
            logger.info(f"Log {log_id}: Delivery failed for {recipient}. Reason: {error_reason}")
            log.status = "failed"
            log.error_message = error_reason
            db.commit()
            add_campaign_event(db, log_id, "failed")
            
    except Exception as e:
        logger.error(f"Failed processing delivery lifecycle for Log {log_id}: {e}")
    finally:
        db.close()

def trigger_outbound_campaign(campaign_id: int, customer_ids: List[int], campaign_topic: str):
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            return
            
        campaign.status = "sending"
        db.commit()

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
            
            # Spin up the background thread to handle delivery and database event logging
            t = threading.Thread(
                target=process_delivery_lifecycle,
                args=(log.id, recipient, channel, msg)
            )
            t.start()
            sent_count += 1
                
        campaign.status = "completed" if sent_count > 0 else "failed"
        db.commit()
        
    except Exception as e:
        logger.error(f"Campaign run error: {e}")
    finally:
        db.close()
