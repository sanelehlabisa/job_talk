from types import SimpleNamespace
from email import policy
from email.parser import BytesParser
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.services import email


@pytest.mark.parametrize(
    "secure,starttls,authenticated",
    [(False, False, False), (False, True, True), (True, False, True)],
)
def test_mailpit_starttls_and_implicit_tls(monkeypatch, secure, starttls, authenticated):
    settings = SimpleNamespace(
        smtp_host="smtp.test.invalid", smtp_port=465 if secure else 587,
        smtp_secure=secure, smtp_user="sender" if authenticated else "",
        smtp_password="test-password" if authenticated else "",
        email_from="login@example.com", recruiter_code_ttl_minutes=10,
    )
    monkeypatch.setattr(email, "get_settings", lambda: settings)
    plain, tls = MagicMock(), MagicMock()
    monkeypatch.setattr(email.smtplib, "SMTP", plain)
    monkeypatch.setattr(email.smtplib, "SMTP_SSL", tls)
    selected, unused = (tls, plain) if secure else (plain, tls)
    smtp = selected.return_value.__enter__.return_value
    smtp.has_extn.return_value = starttls

    email.send_recruiter_login_code("recruiter@example.com", "123456")

    unused.assert_not_called()
    if secure:
        assert selected.call_args.kwargs["context"].check_hostname is True
    if starttls:
        assert smtp.starttls.call_args.kwargs["context"].check_hostname is True
        calls = [call[0] for call in smtp.method_calls]
        assert calls.index("starttls") < calls.index("login")
    else:
        smtp.starttls.assert_not_called()
    assert smtp.login.call_count == int(authenticated)
    message = smtp.send_message.call_args.args[0]
    assert message["From"] == "login@example.com"
    assert message["To"] == "recruiter@example.com"
    parsed = BytesParser(policy=policy.default).parsebytes(message.as_bytes())
    assert [part.get_content_type() for part in parsed.iter_parts()] == ["text/plain", "text/html"]
    plain_body = parsed.get_body(preferencelist=("plain",)).get_content()
    html_body = parsed.get_body(preferencelist=("html",)).get_content()
    for body in (plain_body, html_body):
        assert "123456" in body and "10 minutes" in body
        assert "Do not share this code with anyone." in body
        assert "Use it only to sign in yourself." in body
        assert "The Roventics team" in body
    assert "Select the code to copy." not in html_body
    assert '<script' not in html_body and 'onclick' not in html_body
    assert 'https://roventics.com/images/logo.png' in html_body


def test_smtp_does_not_send_credentials_without_tls(monkeypatch):
    settings = SimpleNamespace(
        smtp_host="smtp.test.invalid", smtp_port=587, smtp_secure=False,
        smtp_user="sender", smtp_password="test-password",
        email_from="login@example.com", recruiter_code_ttl_minutes=10,
    )
    monkeypatch.setattr(email, "get_settings", lambda: settings)
    connection = MagicMock()
    monkeypatch.setattr(email.smtplib, "SMTP", connection)
    smtp = connection.return_value.__enter__.return_value
    smtp.has_extn.return_value = False
    with pytest.raises(RuntimeError, match="must support TLS"):
        email.send_recruiter_login_code("recruiter@example.com", "123456")
    smtp.login.assert_not_called()
    smtp.send_message.assert_not_called()


def test_access_request_contains_only_request_details_and_targets_admin(monkeypatch):
    monkeypatch.setattr(email, "get_settings", lambda: SimpleNamespace(
        admin_email="owner@example.com", email_from="login@example.com",
    ))
    messages = []
    monkeypatch.setattr(email, "_send_message", messages.append)
    email.send_recruiter_access_request("new@example.com", datetime(2026, 10, 7, tzinfo=timezone.utc))
    message = messages[0]
    assert message["To"] == "owner@example.com"
    assert message["From"] == "login@example.com"
    assert "new@example.com" in message.get_content()
    assert "2026-10-07T00:00:00+00:00" in message.get_content()
    assert "pending approval" in message.get_content()
    assert "not yet been verified" in message.get_content()


def test_access_request_without_admin_does_not_send(monkeypatch):
    monkeypatch.setattr(email, "get_settings", lambda: SimpleNamespace(admin_email=None))
    transport = MagicMock()
    monkeypatch.setattr(email, "_send_message", transport)
    email.send_recruiter_access_request("new@example.com", datetime.now(timezone.utc))
    transport.assert_not_called()


def test_login_html_escapes_code_without_changing_plain_text(monkeypatch):
    monkeypatch.setattr(email, "get_settings", lambda: SimpleNamespace(
        smtp_host="smtp.test.invalid", email_from="login@example.com",
        recruiter_code_ttl_minutes=7,
    ))
    messages = []
    monkeypatch.setattr(email, "_send_message", messages.append)
    email.send_recruiter_login_code("recruiter@example.com", '<code>&"')
    message = BytesParser(policy=policy.default).parsebytes(messages[0].as_bytes())
    assert '<code>&"' in message.get_body(preferencelist=("plain",)).get_content()
    html_body = message.get_body(preferencelist=("html",)).get_content()
    assert "&lt;code&gt;&amp;&quot;" in html_body
    assert '<code>' not in html_body
    assert "7 minutes" in html_body
