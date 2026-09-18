"""
Email service
Handles sending emails via SMTP (Mailpit for dev, real SMTP for prod)
"""

import logging
from typing import Optional

from ..config import get_settings

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
) -> bool:
    """
    Send an email using configured SMTP server.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Plain text email body
        html_body: Optional HTML email body
        
    Returns:
        True if email was sent successfully
    """
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        # Create message
        message = MIMEMultipart()
        message["From"] = f"{settings.email_from_name} <{settings.email_from}>"
        message["To"] = to_email
        message["Subject"] = subject
        
        # Add body
        message.attach(MIMEText(body, "plain"))
        
        if html_body:
            message.attach(MIMEText(html_body, "html"))
        
        # Connect to SMTP server
        smtp = aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            use_tls=settings.smtp_use_tls,
        )
        
        if settings.smtp_user and settings.smtp_password:
            await smtp.login(settings.smtp_user, settings.smtp_password)
        
        # Send email
        await smtp.send_message(message)
        await smtp.quit()
        
        logger.info(f"Email sent to {to_email}: {subject}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def send_invite_email(
    to_email: str,
    invite_token: str,
    created_by_email: str,
    frontend_url: str = None,
) -> bool:
    """
    Send an admin invite email.
    
    Args:
        to_email: Email of the user being invited
        invite_token: Invite token for registration
        created_by_email: Email of the admin who created the invite
        frontend_url: Frontend URL (default: from settings)
        
    Returns:
        True if email was sent successfully
    """
    frontend_url = frontend_url or settings.frontend_url
    
    # Build invite URL
    invite_url = f"{frontend_url.rstrip('/')}/register?token={invite_token}"
    
    subject = f"Invitation to join {settings.app_name}"
    
    body = f"""
You have been invited to join {settings.app_name} as an administrator.

To accept this invitation and create your account, please visit:

{invite_url}

This invitation was sent by {created_by_email} and will expire after 24 hours.

If you did not request this invitation, please ignore this email.

---
{settings.app_name} Team
"""
    
    return await send_email(to_email, subject, body)


async def send_password_reset_email(
    to_email: str,
    reset_token: str,
    frontend_url: str = None,
) -> bool:
    """
    Send a password reset email.
    
    Args:
        to_email: Email of the user requesting password reset
        reset_token: Password reset token
        frontend_url: Frontend URL (default: from settings)
        
    Returns:
        True if email was sent successfully
    """
    frontend_url = frontend_url or settings.frontend_url
    
    # Build reset URL
    reset_url = f"{frontend_url.rstrip('/')}/reset-password?token={reset_token}"
    
    subject = f"Password Reset - {settings.app_name}"
    
    body = f"""
You are receiving this email because a password reset was requested for your account.

To reset your password, please visit:

{reset_url}

This link will expire after 1 hour.

If you did not request a password reset, please ignore this email or contact support.

---
{settings.app_name} Team
"""
    
    return await send_email(to_email, subject, body)


async def send_registration_confirmation_email(
    to_email: str,
    full_name: str,
    frontend_url: str = None,
) -> bool:
    """
    Send a registration confirmation email.
    
    Args:
        to_email: Email of the newly registered user
        full_name: User's full name
        frontend_url: Frontend URL (default: from settings)
        
    Returns:
        True if email was sent successfully
    """
    frontend_url = frontend_url or settings.frontend_url
    
    subject = f"Welcome to {settings.app_name}!"
    
    body = f"""
Welcome to {settings.app_name}, {full_name}!

Your account has been successfully created. You can now log in and start using the platform.

Visit {frontend_url} to get started.

---
{settings.app_name} Team
"""
    
    return await send_email(to_email, subject, body)
