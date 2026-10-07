import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage

from ..settings import get_settings


def send_recruiter_login_code(recipient: str, code: str) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.email_from:
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["From"] = str(settings.email_from)
    message["To"] = recipient
    message["Subject"] = "Your Job Talk sign-in code"
    message.set_content(
        f"Your Job Talk sign-in code is {code}. "
        f"It expires in {settings.recruiter_code_ttl_minutes} minutes."
    )
    _send_message(message)


def send_recruiter_access_request(requester: str, requested_at: datetime) -> None:
    settings = get_settings()
    if not settings.admin_email:
        return
    if requested_at.tzinfo is None:
        requested_at = requested_at.replace(tzinfo=timezone.utc)
    message = EmailMessage()
    message["From"] = str(settings.email_from)
    message["To"] = str(settings.admin_email)
    message["Subject"] = "Job Talk: recruiter access request"
    message.set_content(
        f"A new recruiter has requested access to Job Talk.\n\n"
        f"Email: {requester}\n"
        f"Requested at: {requested_at.astimezone(timezone.utc).isoformat()}\n"
        "Status: pending approval\n\n"
        "This email address has not yet been verified. Review the request before approving.\n"
        "Use the existing app.recruiters list / approve commands on the VPS.\n"
        "The requester cannot access recruiter data until approved and signed in.\n"
    )
    _send_message(message)


def _send_message(message: EmailMessage) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.email_from:
        raise RuntimeError("SMTP is not configured")

    connection = (
        smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10,
                         context=ssl.create_default_context())
        if settings.smtp_secure else
        smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    )
    with connection as smtp:
        smtp.ehlo()
        encrypted = settings.smtp_secure
        if not encrypted and smtp.has_extn("starttls"):
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            encrypted = True
        if settings.smtp_user and settings.smtp_password:
            if not encrypted:
                raise RuntimeError("SMTP server must support TLS before authentication")
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
