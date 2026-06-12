from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

from app.services.email import email_service

router = APIRouter()

class LeadNotificationRequest(BaseModel):
    lead_name: str
    lead_email: EmailStr

class ContactEmailRequest(BaseModel):
    name: str
    email: EmailStr
    message: str

class WelcomeEmailRequest(BaseModel):
    name: str
    email: EmailStr

class PasswordResetRequest(BaseModel):
    email: EmailStr
    reset_token: Optional[str] = None

@router.post("/lead", status_code=status.HTTP_200_OK)
def trigger_lead_notification(payload: LeadNotificationRequest):
    """
    Simulates a lead registration event and dispatches an internal team alert.
    """
    res = email_service.sendLeadNotification(
        lead_name=payload.lead_name,
        lead_email=payload.lead_email
    )
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=res.get("error", "Failed to send lead notification email.")
        )
    return {
        "status": "success",
        "message": "Lead notification email sent successfully.",
        "details": res
    }

@router.post("/contact", status_code=status.HTTP_200_OK)
def trigger_contact_email(payload: ContactEmailRequest):
    """
    Simulates contact form submission. Sends auto-confirm to customer and notification to team.
    """
    res = email_service.sendContactEmail(
        recipient_name=payload.name,
        recipient_email=payload.email,
        contact_message=payload.message
    )
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_522_CONNECTION_TIMED_OUT if "timeout" in res.get("error", "").lower() else status.HTTP_502_BAD_GATEWAY,
            detail=res.get("error", "Failed to process contact email workflows.")
        )
    return {
        "status": "success",
        "message": "Contact form auto-confirm and admin alert emails sent successfully.",
        "details": res
    }

@router.post("/welcome", status_code=status.HTTP_200_OK)
def trigger_welcome_email(payload: WelcomeEmailRequest):
    """
    Simulates onboarding and dispatches a welcome email to the client.
    """
    res = email_service.sendWelcomeEmail(
        recipient_name=payload.name,
        recipient_email=payload.email
    )
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=res.get("error", "Failed to send welcome email.")
        )
    return {
        "status": "success",
        "message": "Welcome email sent successfully.",
        "details": res
    }

@router.post("/password-reset", status_code=status.HTTP_200_OK)
def trigger_password_reset(payload: PasswordResetRequest):
    """
    Simulates password reset request and dispatches a recovery email.
    """
    token = payload.reset_token or str(uuid.uuid4())
    res = email_service.sendPasswordResetEmail(
        recipient_email=payload.email,
        reset_token=token
    )
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=res.get("error", "Failed to send password reset email.")
        )
    return {
        "status": "success",
        "message": "Password reset email sent successfully.",
        "token": token,
        "details": res
    }
