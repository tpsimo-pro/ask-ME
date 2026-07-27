import logging
import re
import smtplib
from email.mime.text import MIMEText
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_QUERY_PARAM = re.compile(r"(token=)[^&\s]+")


def _mask_tokens(text: str) -> str:
    return _TOKEN_QUERY_PARAM.sub(r"\1***redacted***", text)


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Writes a token-redacted version of the message to the application log.

    Dev and docker-compose default only. `get_email_sender` never returns
    this outside `settings.environment == "development"`.
    """

    def send(self, to: str, subject: str, body: str) -> None:
        logger.warning(
            "\n--- EMAIL (dev, token redacted) ---\nFrom: %s\nTo: %s\nSubject: %s\n\n%s\n-------------",
            settings.email_from,
            to,
            subject,
            _mask_tokens(body),
        )


class SmtpEmailSender:
    """Sends mail via SMTP. Used whenever settings.environment != 'development'."""

    def send(self, to: str, subject: str, body: str) -> None:
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = settings.email_from
        message["To"] = to

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)


def get_email_sender() -> EmailSender:
    if settings.environment == "development":
        return ConsoleEmailSender()

    if not settings.smtp_host:
        raise RuntimeError(
            "settings.smtp_host is required when settings.environment != 'development'"
        )
    return SmtpEmailSender()
