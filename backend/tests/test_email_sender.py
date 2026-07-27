import logging

from app.auth.email_sender import ConsoleEmailSender, SmtpEmailSender, get_email_sender


def test_console_sender_masks_token_in_body(caplog):
    body = "Clique aqui: http://localhost:5173/reset-password?token=abcdef1234567890"

    with caplog.at_level(logging.WARNING):
        ConsoleEmailSender().send("user@example.com", "Assunto", body)

    logged = caplog.text
    assert "abcdef1234567890" not in logged
    assert "token=***redacted***" in logged


def test_get_email_sender_returns_console_in_development(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "development")
    assert isinstance(get_email_sender(), ConsoleEmailSender)


def test_get_email_sender_returns_smtp_in_production(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    assert isinstance(get_email_sender(), SmtpEmailSender)


def test_smtp_sender_requires_smtp_host(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_host", "")

    try:
        get_email_sender()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "smtp_host" in str(exc)
