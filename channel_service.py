from fastapi import FastAPI, BackgroundTasks, status
from pydantic import BaseModel
import httpx
import random
import time
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ChannelService")

app = FastAPI(title="Xeno Mock Channel Service", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "Mock Channel Service is running."}

import os
from dotenv import load_dotenv
from app.services.email import email_service

# Try loading .env from current directory or Frontend directory
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "Frontend", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "Frontend", ".env"))

CRM_BACKEND_HOST = os.getenv("CRM_BACKEND_HOST")
if CRM_BACKEND_HOST:
    CRM_CALLBACK_URL = f"http://{CRM_BACKEND_HOST}/api/v1/campaigns/callback"
else:
    CRM_CALLBACK_URL = os.getenv("CRM_CALLBACK_URL", "http://127.0.0.1:8000/api/v1/campaigns/callback")

class OutboundMessage(BaseModel):
    log_id: int
    recipient: str
    message: str
    channel: str # sms, whatsapp, email

def simulate_delivery_lifecycle(log_id: int, recipient: str, channel: str, message: str):
    client = httpx.Client()
    try:
        # --- PHASE 1: Delivery status ---
        time.sleep(random.uniform(1.0, 2.0))
        
        is_success = False
        if channel == "email" and os.getenv("BREVO_API_KEY"):
            logger.info(f"Log {log_id}: Dispatching email to {recipient} via Brevo API...")
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
                    <h2 style="color: #2563eb; margin-top: 0;">PulseCRM Campaign Outbound</h2>
                    <p style="font-size: 16px; white-space: pre-wrap;">{message}</p>
                    <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;">
                    <p style="font-size: 12px; color: #888888; margin-bottom: 0;">Sent via PulseCRM Campaign Engine.</p>
                </div>
            </body>
            </html>
            """
            res = email_service.sendEmail(
                recipient_email=recipient,
                subject="Exclusive PulseCRM Campaign Offer",
                html_content=html_content,
                text_content=message
            )
            is_success = res.get("success", False)
        else:
            reason = "Channel is not email" if channel != "email" else "BREVO_API_KEY env variable is not set"
            logger.info(f"Log {log_id}: Simulating delivery locally. (Reason: {reason})")
            # Fallback to local mock simulation
            is_success = random.random() < 0.90
        
        if is_success:
            logger.info(f"Log {log_id}: Message delivered to {recipient} via {channel}.")
            client.post(CRM_CALLBACK_URL, json={
                "log_id": log_id,
                "status": "delivered"
            })
            
            # --- PHASE 2: Open status ---
            time.sleep(random.uniform(2.0, 4.0))
            is_opened = random.random() < 0.60
            if is_opened:
                logger.info(f"Log {log_id}: Message opened by {recipient}.")
                client.post(CRM_CALLBACK_URL, json={
                    "log_id": log_id,
                    "status": "opened"
                })
                
                # --- PHASE 3: Click status ---
                time.sleep(random.uniform(1.0, 3.0))
                is_clicked = random.random() < 0.30
                if is_clicked:
                    logger.info(f"Log {log_id}: Link clicked by {recipient}.")
                    client.post(CRM_CALLBACK_URL, json={
                        "log_id": log_id,
                        "status": "clicked"
                    })
        else:
            error_reason = "Brevo transmission error" if channel == "email" else random.choice([
                "Invalid recipient address",
                "Inbox capacity exceeded",
                "Carrier routing failure"
            ])
            logger.info(f"Log {log_id}: Delivery failed for {recipient}. Reason: {error_reason}")
            client.post(CRM_CALLBACK_URL, json={
                "log_id": log_id,
                "status": "failed",
                "error_message": error_reason
            })
            
    except Exception as e:
        logger.error(f"Failed to post callback to CRM for Log {log_id}: {e}")
    finally:
        client.close()

@app.post("/send", status_code=status.HTTP_202_ACCEPTED)
def send_message(msg: OutboundMessage, background_tasks: BackgroundTasks):
    logger.info(f"Received outbound request for Log {msg.log_id} to {msg.recipient}")
    background_tasks.add_task(
        simulate_delivery_lifecycle, 
        msg.log_id, 
        msg.recipient, 
        msg.channel,
        msg.message
    )
    return {"status": "accepted", "message": "Delivery process started."}
