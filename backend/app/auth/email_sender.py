import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Writes the message to the application log.

    Dev and docker-compose default: the password-reset link is readable in
    `docker compose logs backend`, so the whole flow is exercisable without a
    third-party provider. Production swaps in a real sender here.
    """

    def send(self, to: str, subject: str, body: str) -> None:
        logger.warning(
            "\n--- EMAIL ---\nFrom: %s\nTo: %s\nSubject: %s\n\n%s\n-------------",
            settings.email_from,
            to,
            subject,
            body,
        )


def get_email_sender() -> EmailSender:
    return ConsoleEmailSender()
