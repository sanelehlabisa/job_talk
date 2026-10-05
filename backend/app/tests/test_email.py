from types import SimpleNamespace
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
    assert "123456" in message.get_content()


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
