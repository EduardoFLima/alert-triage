"""Delivering a triage report as mail.

What a report looks like as an email, and what it means for one to have been
submitted. The SMTP client itself, and every ``smtplib`` type behind it, lives
in ``smtp``.

Note the hazard this module lives with: its own package is
``alert_triage.notification.adapters.email``, and the standard library module
it needs is ``email``. Absolute imports are what make ``from email.message import
EmailMessage`` below resolve to the standard library, and a test asserts
exactly that — a relative import would shadow it in a way only a deployed run
would notice.
"""

import smtplib
from email.message import EmailMessage

from alert_triage.notification.adapters.email.settings import EmailSettings
from alert_triage.notification.adapters.email.smtp import (
    SmtpClient,
    SmtpFactory,
    attempt_starttls,
    open_smtp,
)
from alert_triage.notification.contract import TriageReport
from alert_triage.notification.ports.notifier import NotifierError


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
    rule as the Datadog adapter's client and the ledger's connection: it is
    what lets these tests run with no mail server at all.
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
        self._smtp = smtp if smtp is not None else open_smtp(settings)

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
        """Establish who we are to the relay, then hand the message over."""
        self._authenticate(server)
        server.send_message(message)

    def _authenticate(self, server: SmtpClient) -> None:
        """Secure the connection, and log in only if it actually got secured.

        The two belong in one place: secrecy is required exactly when there is
        a secret to keep. A relay offering no STARTTLS still takes the report,
        because an unauthenticated relay is a deployment this project supports
        — but a configured password is never spent on a connection in the
        clear.
        """
        secured = attempt_starttls(server)
        credentials = self._settings.credentials
        if credentials is None:
            return
        if not secured:
            raise self._cleartext_refusal()
        server.login(*credentials)

    def _cleartext_refusal(self) -> NotifierError:
        """Say why a configured password was not spent on this connection."""
        return NotifierError(
            f"{self._settings.host} does not offer STARTTLS, and "
            f"{self._settings.username!r}'s password will not be sent in the "
            f"clear. Use a relay that offers STARTTLS, or configure the channel "
            f"without credentials."
        )
