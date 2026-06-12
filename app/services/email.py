import os
import time
import logging
import httpx
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("EmailService")

class EmailService:
    def __init__(self):
        # Read environment variables
        self.api_key = os.getenv("BREVO_API_KEY")
        self.email_from = os.getenv("EMAIL_FROM", "noreply@akshatsahay.space")
        self.api_url = "https://api.brevo.com/v3/smtp/email"

    def _get_premium_html_wrapper(self, title: str, inner_html: str) -> str:
        """Wraps inner HTML in a premium, responsive container with elegant styles."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background-color: #f8fafc;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                    -webkit-font-smoothing: antialiased;
                    -moz-osx-font-smoothing: grayscale;
                    color: #334155;
                }}
                .container {{
                    max-width: 600px;
                    margin: 40px auto;
                    padding: 0 20px;
                }}
                .card {{
                    background: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #2563eb, #1d4ed8);
                    color: #ffffff;
                    padding: 32px 24px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                    font-weight: 700;
                    letter-spacing: -0.025em;
                }}
                .content {{
                    padding: 32px 24px;
                    line-height: 1.6;
                }}
                .content p {{
                    margin-top: 0;
                    margin-bottom: 16px;
                }}
                .btn {{
                    display: inline-block;
                    background-color: #2563eb;
                    color: #ffffff !important;
                    text-decoration: none;
                    padding: 12px 24px;
                    border-radius: 6px;
                    font-weight: 600;
                    margin: 16px 0;
                    text-align: center;
                }}
                .btn:hover {{
                    background-color: #1d4ed8;
                }}
                .footer {{
                    background-color: #f1f5f9;
                    padding: 24px;
                    text-align: center;
                    font-size: 12px;
                    color: #64748b;
                    border-top: 1px solid #e2e8f0;
                }}
                .footer p {{
                    margin: 4px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="header">
                        <h1>{title}</h1>
                    </div>
                    <div class="content">
                        {inner_html}
                    </div>
                    <div class="footer">
                        <p>Sent via <strong>PulseCRM</strong></p>
                        <p>&copy; {time.strftime('%Y')} PulseCRM Team. All rights reserved.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    def sendEmail(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        recipient_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends an email using Brevo's Transactional API with retry and timeout logic.
        Never crashes the application. Returns structured success/error response.
        """
        if not self.api_key:
            err_msg = "BREVO_API_KEY not configured in environment variables."
            logger.warning(err_msg)
            return {"success": False, "error": err_msg}

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json"
        }

        payload = {
            "sender": {
                "name": "PulseCRM Team",
                "email": self.email_from
            },
            "to": [
                {
                    "email": recipient_email,
                    "name": recipient_name or recipient_email.split("@")[0]
                }
            ],
            "subject": subject,
            "htmlContent": html_content,
            "textContent": text_content or ""
        }

        max_retries = 3
        timeout_seconds = 10.0

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Attempting to send email to {recipient_email} (Attempt {attempt}/{max_retries})")
                with httpx.Client(timeout=timeout_seconds) as client:
                    response = client.post(self.api_url, headers=headers, json=payload)
                    
                    if response.status_code in [200, 201, 202]:
                        resp_data = response.json()
                        message_id = resp_data.get("messageId", "")
                        logger.info(f"Successful email send to {recipient_email}. Message ID: {message_id}")
                        return {
                            "success": True,
                            "message_id": message_id,
                            "status_code": response.status_code
                        }
                    else:
                        logger.error(
                            f"API error on attempt {attempt}: Status {response.status_code} - {response.text}"
                        )
                        # API returned an error, backoff and retry
            except httpx.RequestError as exc:
                logger.error(f"Request exception on attempt {attempt}: {exc}")
            
            # Exponential backoff (1s, 2s, 4s...)
            if attempt < max_retries:
                sleep_time = 2 ** attempt
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)

        logger.error(f"Failed email send to {recipient_email} after {max_retries} attempts.")
        return {
            "success": False,
            "error": f"Failed to send email after {max_retries} attempts."
        }

    def sendLeadNotification(self, lead_name: str, lead_email: str) -> Dict[str, Any]:
        """Dispatches an internal alert email to the team regarding a new signup/lead."""
        subject = f"New Lead Registered: {lead_name}"
        inner_html = f"""
        <p>Hello PulseCRM Team,</p>
        <p>A new lead has just registered on the platform. Here are the details:</p>
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px;">
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; font-weight: 600; width: 30%;">Name:</td>
                <td style="padding: 8px 0; color: #475569;">{lead_name}</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; font-weight: 600;">Email:</td>
                <td style="padding: 8px 0; color: #475569;">{lead_email}</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; font-weight: 600;">Signup Time:</td>
                <td style="padding: 8px 0; color: #475569;">{time.strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
            </tr>
        </table>
        <p>You can view and manage this lead directly in your PulseCRM Admin Dashboard.</p>
        """
        html_content = self._get_premium_html_wrapper("New Lead Alert", inner_html)
        text_content = f"New Lead Alert:\nName: {lead_name}\nEmail: {lead_email}\nSignup Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        # Send to administration (configured default sender)
        return self.sendEmail(
            recipient_email=self.email_from,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            recipient_name="PulseCRM Admin"
        )

    def sendContactEmail(self, recipient_name: str, recipient_email: str, contact_message: str) -> Dict[str, Any]:
        """
        Processes contact form submission.
        1. Sends confirmation email to user.
        2. Sends admin alert email with the message payload.
        """
        # 1. User confirmation
        user_subject = "We received your message - PulseCRM Support"
        user_inner = f"""
        <p>Dear {recipient_name},</p>
        <p>Thank you for reaching out to us. We have received your query and our team is already looking into it.</p>
        <div style="background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 16px; margin: 20px 0; font-style: italic; color: #475569;">
            "{contact_message}"
        </div>
        <p>A support representative will contact you at this email address within the next 24 hours.</p>
        <p>Best regards,<br>PulseCRM Support Team</p>
        """
        user_html = self._get_premium_html_wrapper("Support Request Received", user_inner)
        user_text = f"Dear {recipient_name},\nThank you for reaching out. We received your message: '{contact_message}'. We will respond within 24 hours."
        
        user_res = self.sendEmail(
            recipient_email=recipient_email,
            subject=user_subject,
            html_content=user_html,
            text_content=user_text,
            recipient_name=recipient_name
        )

        # 2. Admin notification
        admin_subject = f"Contact Form Submission from {recipient_name}"
        admin_inner = f"""
        <p>Hello PulseCRM Admin,</p>
        <p>A visitor has submitted a message via the website contact form.</p>
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px;">
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; font-weight: 600; width: 30%;">Name:</td>
                <td style="padding: 8px 0; color: #475569;">{recipient_name}</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px 0; font-weight: 600;">Email:</td>
                <td style="padding: 8px 0; color: #475569;">{recipient_email}</td>
            </tr>
        </table>
        <p><strong>Message:</strong></p>
        <div style="background-color: #f1f5f9; padding: 16px; border-radius: 8px; font-size: 14px; white-space: pre-wrap; color: #334155;">{contact_message}</div>
        """
        admin_html = self._get_premium_html_wrapper("New Contact Form Query", admin_inner)
        admin_text = f"Contact Form Query:\nFrom: {recipient_name} ({recipient_email})\nMessage: {contact_message}"
        
        admin_res = self.sendEmail(
            recipient_email=self.email_from,
            subject=admin_subject,
            html_content=admin_html,
            text_content=admin_text,
            recipient_name="PulseCRM Admin"
        )

        return {
            "user_confirmation": user_res,
            "admin_notification": admin_res,
            "success": user_res.get("success", False) and admin_res.get("success", False)
        }

    def sendWelcomeEmail(self, recipient_name: str, recipient_email: str) -> Dict[str, Any]:
        """Sends a beautiful onboarding welcome email to a new user."""
        subject = "Welcome to PulseCRM - Let's get started!"
        inner_html = f"""
        <p>Hello {recipient_name},</p>
        <p>Welcome to the <strong>PulseCRM</strong> family! We're excited to have you on board.</p>
        <p>PulseCRM helps you manage customer interactions, build automated segments, and design campaigns powered by cutting-edge AI. Here are your next steps to get started:</p>
        <ol style="padding-left: 20px; color: #475569;">
            <li style="margin-bottom: 8px;"><strong>Complete Your Profile:</strong> Fill in your business details.</li>
            <li style="margin-bottom: 8px;"><strong>Import Contacts:</strong> Populate your customer database.</li>
            <li style="margin-bottom: 8px;"><strong>Build Segments:</strong> Organize contacts by spending or behavior.</li>
            <li style="margin-bottom: 8px;"><strong>Launch AI Campaigns:</strong> Write and send high-converting emails.</li>
        </ol>
        <div style="text-align: center; margin: 32px 0;">
            <a href="https://akshatsahay.space/dashboard" class="btn">Access CRM Dashboard</a>
        </div>
        <p>If you have any questions or need help setting up, feel free to reply to this email.</p>
        <p>Cheers,<br>The PulseCRM Team</p>
        """
        html_content = self._get_premium_html_wrapper("Welcome to PulseCRM", inner_html)
        text_content = f"Hello {recipient_name},\nWelcome to PulseCRM! We help you manage customer relationships and run AI-powered campaigns. Access your dashboard at: https://akshatsahay.space/dashboard"
        
        return self.sendEmail(
            recipient_email=recipient_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            recipient_name=recipient_name
        )

    def sendPasswordResetEmail(self, recipient_email: str, reset_token: str) -> Dict[str, Any]:
        """Dispatches a secure password recovery email containing tokenized links."""
        subject = "Reset Your PulseCRM Password"
        reset_link = f"https://akshatsahay.space/reset-password?token={reset_token}"
        inner_html = f"""
        <p>Hello,</p>
        <p>We received a request to reset the password for your PulseCRM account. Click the button below to set a new password:</p>
        <div style="text-align: center; margin: 32px 0;">
            <a href="{reset_link}" class="btn">Reset Password</a>
        </div>
        <p>Or copy and paste this URL into your browser:</p>
        <p style="word-break: break-all; font-size: 14px; color: #2563eb;"><a href="{reset_link}">{reset_link}</a></p>
        <p style="color: #64748b; font-size: 13px;"><strong>Note:</strong> This link is secure and will expire in 1 hour. If you did not request a password reset, you can safely ignore this email.</p>
        """
        html_content = self._get_premium_html_wrapper("Password Reset Request", inner_html)
        text_content = f"Password Reset Request:\nReset your password using the following link: {reset_link}\nThis link expires in 1 hour."
        
        return self.sendEmail(
            recipient_email=recipient_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )

# Centralized singleton service instance
email_service = EmailService()
