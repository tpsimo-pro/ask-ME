import logging
import ssl
from unittest.mock import MagicMock, patch

from app.auth.email_sender import ConsoleEmailSender, SmtpEmailSender, get_email_sender


def test_console_sender_masks_token_in_body(caplog):
    body = "Clique aqui: http://localhost:5173/reset-password?token=abcdef1234567890"

    with caplog.at_level(logging.WARNING):
        ConsoleEmailSender().send("user@example.com", "Assunto", body)

    logged = caplog.text
    assert "abcdef1234567890" not in logged
    assert "token=***redacted***" in logged


def test_get_email_sender_returns_console_in_development_without_smtp_host(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "smtp_host", "")
    assert isinstance(get_email_sender(), ConsoleEmailSender)


def test_get_email_sender_returns_smtp_in_production(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    assert isinstance(get_email_sender(), SmtpEmailSender)


def test_get_email_sender_returns_smtp_in_development_when_smtp_host_configured(monkeypatch):
    """Dev can carry real SMTP creds without flipping `environment` to production."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    assert isinstance(get_email_sender(), SmtpEmailSender)


def test_smtp_sender_requires_smtp_host_outside_development(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_host", "")

    try:
        get_email_sender()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "smtp_host" in str(exc)


def test_smtp_sender_starttls_uses_a_verifying_ssl_context(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_use_tls", True)
    monkeypatch.setattr(settings, "smtp_username", "")

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance

    with patch("smtplib.SMTP", return_value=mock_smtp_instance) as mock_smtp_cls:
        SmtpEmailSender().send("user@example.com", "Assunto", "Corpo")

    mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=10)
    mock_smtp_instance.starttls.assert_called_once()
    _, kwargs = mock_smtp_instance.starttls.call_args
    assert "context" in kwargs
    assert isinstance(kwargs["context"], ssl.SSLContext)
