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

def simulate_delivery_lifecycle(log_id: int, recipient: str, channel: str, message: str):
    client = httpx.Client()
    try:
        # --- PHASE 1: Delivery status ---
        time.sleep(random.uniform(1.0, 2.0))
        
        is_success = False
        if channel == "email" and os.getenv("BREVO_API_KEY"):
            logger.info(f"Log {log_id}: Dispatching email to {recipient} via Brevo API...")
            is_success = send_email_via_brevo(recipient, message)
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
