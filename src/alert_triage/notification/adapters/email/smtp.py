import smtplib
from collections.abc import Callable
from contextlib import AbstractContextManager
from email.message import EmailMessage
from typing import Protocol

from alert_triage.notification.adapters.email.settings import EmailSettings

# A hung relay must not hold a run open. Fixed rather than configurable: there
# is no evidence yet of what an operator would tune it against, and a run that
# delivered nothing is retried by the next one anyway.
TIMEOUT_SECONDS = 30


class SmtpClient(Protocol):
    def starttls(self) -> object: ...

    def login(self, username: str, password: str) -> object: ...

    def send_message(self, message: EmailMessage) -> object: ...


type SmtpFactory = Callable[[], AbstractContextManager[SmtpClient]]


def open_smtp(settings: EmailSettings) -> SmtpFactory:

    def open_connection() -> smtplib.SMTP:
        return smtplib.SMTP(settings.host, settings.port, timeout=TIMEOUT_SECONDS)

    return open_connection


def attempt_starttls(client: SmtpClient) -> bool:
    try:
        client.starttls()
    except smtplib.SMTPNotSupportedError:
        return False
    return True
