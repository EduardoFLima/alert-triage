"""The SMTP client this adapter submits through, and how one is opened.

Every ``smtplib`` type the adapter touches lives here, so ``notifier`` is left
with what a report *is* on this channel rather than how a connection to a
relay behaves.
"""

import smtplib
from collections.abc import Callable
from contextlib import AbstractContextManager
from email.message import EmailMessage
from typing import Protocol

from alert_triage.adapters.email.settings import EmailSettings

# A hung relay must not hold a run open. Fixed rather than configurable: there
# is no evidence yet of what an operator would tune it against, and a run that
# delivered nothing is retried by the next one anyway.
TIMEOUT_SECONDS = 30


class SmtpClient(Protocol):
    """The three calls this adapter makes, named so a test can stand in for them.

    Narrower than ``smtplib.SMTP`` on purpose, exactly as the Datadog adapter
    names the one endpoint it uses. Each call is declared as answering
    ``object`` because the adapter reads none of the answers — ``smtplib``
    signals failure by raising, and a fake should not have to invent a reply
    code to be substitutable.
    """

    def starttls(self) -> object:
        """Secure the connection, or raise if the server does not offer it."""
        ...

    def login(self, username: str, password: str) -> object:
        """Authenticate to the server."""
        ...

    def send_message(self, message: EmailMessage) -> object:
        """Hand the message over for delivery."""
        ...


type SmtpFactory = Callable[[], AbstractContextManager[SmtpClient]]


def open_smtp(settings: EmailSettings) -> SmtpFactory:
    """Open a connection to the configured relay, bounded by the fixed timeout.

    A factory rather than a connection: ``smtplib`` is shaped for a connection
    per submission, and taking the factory is what lets the notifier's tests
    run with no mail server at all.
    """

    def open_connection() -> smtplib.SMTP:
        return smtplib.SMTP(settings.host, settings.port, timeout=TIMEOUT_SECONDS)

    return open_connection


def attempt_starttls(client: SmtpClient) -> bool:
    """Secure the connection if the relay offers it, saying whether it did.

    Attempted rather than required: a plain relay on a container's own network
    is a deployment this project anticipates — it is why the credentials are
    optional — and refusing it outright would rule that deployment out. What is
    never negotiable is a *password* over an unencrypted connection, and that
    is the caller's decision to make with this answer.
    """
    try:
        client.starttls()
    except smtplib.SMTPNotSupportedError:
        return False
    return True
