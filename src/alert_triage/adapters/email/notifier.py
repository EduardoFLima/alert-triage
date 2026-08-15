"""Delivering a triage report as mail, over the standard library's ``smtplib``.

Everything mail-shaped stops here: the MIME message, STARTTLS, the login, and
``smtplib``'s own exceptions. What leaves is nothing, or a ``NotifierError``.

Note the hazard this module lives with: its own package is
``alert_triage.adapters.email``, and the standard library module it needs is
``email``. Absolute imports are what make ``from email.message import
EmailMessage`` below resolve to the standard library, and a test asserts
exactly that — a relative import would shadow it in a way only a deployed run
would notice.
"""

import smtplib
from collections.abc import Callable
from contextlib import AbstractContextManager
from email.message import EmailMessage
from typing import Protocol

from alert_triage.adapters.email.settings import EmailSettings
from alert_triage.domain.report import TriageReport
from alert_triage.ports.notifier import NotifierError

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


def render(report: TriageReport, settings: EmailSettings) -> EmailMessage:
    """Render a report as the mail message that carries it.

    Pure, so the shape of what gets sent is tested without a mail server.

    Args:
        report: The report to render.
        settings: Who the mail is from and who it goes to.

    Returns:
        A plain-text message carrying the report's subject and body verbatim.
    """
    message = EmailMessage()
    message["Subject"] = report.subject
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message.set_content(report.body)
    return message


class EmailNotifier:
    """A ``Notifier`` that submits each report to an SMTP server.

    The client is injected as a factory rather than opened here, on the same
    rule as the Datadog adapter's client and the ledger's connection: a
    connection per delivery is what ``smtplib`` is shaped for, and taking the
    factory is what lets these tests run with no mail server at all.
    """

    def __init__(
        self, settings: EmailSettings, smtp: SmtpFactory | None = None
    ) -> None:
        """Bind the channel to its destination and the client it submits through.

        Args:
            settings: Where to submit, as whom, and to whom.
            smtp: Opens a connection to the submission server. Defaults to
                ``smtplib.SMTP`` against the configured host and port.
        """
        self._settings = settings
        self._smtp = smtp if smtp is not None else _default_smtp(settings)

    def deliver(self, report: TriageReport) -> None:
        """Submit the report as mail to every configured recipient.

        This is the boundary: past it a caller catches ``NotifierError`` and
        never learns SMTP was involved. Failing here rather than returning is
        what stops a cooldown starting on a report nobody received.
        """
        try:
            with self._smtp() as server:
                self._submit(server, render(report, self._settings))
        except (smtplib.SMTPException, OSError) as error:
            raise NotifierError(
                f"Could not email the report for incident {report.incident_id!r} "
                f"to {', '.join(self._settings.recipients)} via "
                f"{self._settings.host}: {error}"
            ) from error

    def _submit(self, server: SmtpClient, message: EmailMessage) -> None:
        """Secure the connection, authenticate if asked to, and hand over the mail."""
        secured = _secured(server)
        credentials = self._settings.credentials
        if credentials is not None:
            if not secured:
                raise NotifierError(
                    f"{self._settings.host} does not offer STARTTLS, and "
                    f"{self._settings.username!r}'s password will not be sent in "
                    f"the clear. Use a relay that offers STARTTLS, or configure "
                    f"the channel without credentials."
                )
            server.login(*credentials)
        server.send_message(message)


def _default_smtp(settings: EmailSettings) -> SmtpFactory:
    """Open a connection to the configured relay, bounded by the fixed timeout."""

    def open_connection() -> smtplib.SMTP:
        return smtplib.SMTP(settings.host, settings.port, timeout=TIMEOUT_SECONDS)

    return open_connection


def _secured(server: SmtpClient) -> bool:
    """Attempt STARTTLS, answering whether the connection ended up encrypted.

    Attempted rather than required: a plain relay on a container's own network
    is a deployment this project anticipates — it is why the credentials are
    optional — and refusing it outright would rule that deployment out. What is
    never negotiable is a *password* over an unencrypted connection, which is
    the caller's business and is refused there.
    """
    try:
        server.starttls()
    except smtplib.SMTPNotSupportedError:
        return False
    return True
