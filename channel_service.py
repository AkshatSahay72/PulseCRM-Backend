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

import os

CRM_CALLBACK_URL = os.getenv("CRM_CALLBACK_URL", "http://127.0.0.1:8000/api/v1/campaigns/callback")

class OutboundMessage(BaseModel):
    log_id: int
    recipient: str
    message: str
    channel: str # sms, whatsapp, email

def simulate_delivery_lifecycle(log_id: int, recipient: str, channel: str):
    """
    Simulates the asynchronous message delivery lifecycle:
    1. Wait 1-2s -> Send Delivered (90% success) or Failed (10% failure)
    2. If delivered, Wait 2-4s -> Send Opened (60% chance)
    3. If opened, Wait 1-3s -> Send Clicked (30% chance)
    """
    client = httpx.Client()
    try:
        # --- PHASE 1: Delivery status ---
        time.sleep(random.uniform(1.0, 2.0))
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
            error_reason = random.choice([
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
    """
    Accepts sending request, returns 202 immediately, 
    and simulates lifecycle asynchronously in a background task.
    """
    logger.info(f"Received outbound request for Log {msg.log_id} to {msg.recipient}")
    background_tasks.add_task(
        simulate_delivery_lifecycle, 
        msg.log_id, 
        msg.recipient, 
        msg.channel
    )
    return {"status": "accepted", "message": "Delivery process started."}
