import smtplib
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

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
