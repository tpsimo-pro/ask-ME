import logging
import re
import smtplib
import ssl
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

    Fallback for whenever SMTP isn't configured (`settings.smtp_host` blank).
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
    """Sends mail via SMTP. Used whenever settings.smtp_host is configured."""

    def send(self, to: str, subject: str, body: str) -> None:
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = settings.email_from
        message["To"] = to

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)


def get_email_sender() -> EmailSender:
    """Use real SMTP whenever it's configured, regardless of environment.

    This is decoupled from `settings.environment` on purpose: dev can carry
    real SMTP credentials in `.env` without flipping `environment` to
    production (which gates unrelated prod-only behavior, e.g. the boot-time
    validator below). Outside development, `Settings.smtp_host_required_outside_development`
    already fails at boot if `smtp_host` is blank, so reaching this function
    with `environment != "development"` and no `smtp_host` should be
    unreachable in practice -- the explicit check here is a defense-in-depth
    safety net against that invariant being bypassed (e.g. settings mutated
    at runtime).
    """
    if settings.smtp_host:
        return SmtpEmailSender()

    if settings.environment != "development":
        raise RuntimeError(
            "settings.smtp_host is required when settings.environment != 'development'"
        )
    return ConsoleEmailSender()
