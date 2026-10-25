import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape

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
        f"Your Job Talk sign-in code is {code}.\n"
        f"It expires in {settings.recruiter_code_ttl_minutes} minutes.\n\n"
        "Do not share this code with anyone. Use it only to sign in yourself.\n"
        "If you did not request this code, you can ignore this email.\n\n"
        "The Roventics team\nRoventics (Pty) Ltd\nhttps://roventics.com\n"
    )
    message.add_alternative(f"""<!doctype html>
<html lang="en"><body style="margin:0;background:#f4f4f4;color:#111;font-family:Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff">
<tr><td style="padding:24px">
<h1 style="margin:0 0 16px;font-size:24px">Sign in to Job Talk</h1>
<p style="margin:0 0 20px;line-height:1.5">Enter this code in Job Talk to sign in.</p>
<p style="margin:0 0 20px;padding:20px;background:#f2f2f2;text-align:center;font-family:monospace;font-size:32px;font-weight:700;letter-spacing:4px">{escape(code)}</p>
<p style="margin:0 0 16px;line-height:1.5">This code expires in {settings.recruiter_code_ttl_minutes} minutes.</p>
<p style="margin:0 0 16px;line-height:1.5"><strong>Do not share this code with anyone.</strong> Use it only to sign in yourself.</p>
<p style="margin:0 0 24px;color:#666;font-size:14px;line-height:1.5">If you did not request this code, you can ignore this email.</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-top:1px solid #ddd"><tr>
<td width="44" style="padding-top:20px;vertical-align:top"><img src="https://roventics.com/images/logo.png" alt="Roventics" width="32" height="32" style="display:block;border:0"></td>
<td style="padding-top:20px;font-size:13px;color:#666;line-height:1.6"><strong style="color:#111">The Roventics team</strong><br>Roventics (Pty) Ltd &middot; <a href="https://roventics.com" style="color:#111">roventics.com</a></td>
</tr></table>
</td></tr></table>
</td></tr></table></body></html>""", subtype="html")
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
