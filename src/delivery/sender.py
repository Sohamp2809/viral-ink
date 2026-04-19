"""
Email Sender — dispatches HTML emails via Resend API or SMTP fallback.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiohttp

from src.utils.config import get_settings

logger = logging.getLogger(__name__)


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    from_email: str | None = None,
) -> bool:
    """
    Send an HTML email. Tries Resend API first, falls back to SMTP.

    Returns True if sent successfully.
    """
    settings = get_settings()

    resend_key = getattr(settings, "resend_api_key", "")
    if resend_key and resend_key != "re_xxxxx":
        return await _send_resend(to, subject, html_body, from_email or "pilot@resend.dev", resend_key)

    smtp_host = getattr(settings, "smtp_host", "")
    if smtp_host:
        return _send_smtp(to, subject, html_body, from_email, settings)

    logger.error(
        "No email provider configured. Set RESEND_API_KEY or SMTP_HOST in .env"
    )
    return False


async def _send_resend(
    to: str, subject: str, html: str, from_email: str, api_key: str
) -> bool:
    """Send via Resend API."""
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://api.resend.com/emails",
                json={
                    "from": from_email,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            )

            if resp.status in (200, 201):
                data = await resp.json()
                logger.info(f"Email sent via Resend: {data.get('id', 'ok')}")
                return True
            else:
                body = await resp.text()
                logger.error(f"Resend error {resp.status}: {body[:200]}")
                return False

    except Exception as e:
        logger.error(f"Resend send failed: {e}")
        return False


def _send_smtp(
    to: str, subject: str, html: str, from_email: str | None, settings
) -> bool:
    """Send via SMTP."""
    try:
        host = settings.smtp_host
        port = getattr(settings, "smtp_port", 587)
        user = getattr(settings, "smtp_user", "")
        password = getattr(settings, "smtp_password", "")
        sender = from_email or user

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(sender, [to], msg.as_string())

        logger.info(f"Email sent via SMTP to {to}")
        return True

    except Exception as e:
        logger.error(f"SMTP send failed: {e}")
        return False


async def send_daily_email(
    posts: list,
    trends: list,
) -> bool:
    """
    Build and send the daily post suggestions email.
    """
    settings = get_settings()
    to = getattr(settings, "email_to", "")

    if not to:
        logger.warning("EMAIL_TO not configured — skipping email delivery")
        return False

    from src.delivery.email_builder import build_email_html

    subject, html = build_email_html(posts, trends)

    logger.info(f"Sending daily email to {to}...")
    return await send_email(to, subject, html)