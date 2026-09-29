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
    message = EmailMessage()
    message["Subject"] = report.subject
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message.set_content(report.body)
    return message


class EmailNotifier:
    def __init__(
        self, settings: EmailSettings, smtp: SmtpFactory | None = None
    ) -> None:
        self._settings = settings
        self._smtp = smtp if smtp is not None else open_smtp(settings)

    def deliver(self, report: TriageReport) -> None:
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
        self._authenticate(server)
        server.send_message(message)

    def _authenticate(self, server: SmtpClient) -> None:
        secured = attempt_starttls(server)
        credentials = self._settings.credentials
        if credentials is None:
            return
        if not secured:
            raise self._cleartext_refusal()
        server.login(*credentials)

    def _cleartext_refusal(self) -> NotifierError:
        return NotifierError(
            f"{self._settings.host} does not offer STARTTLS, and "
            f"{self._settings.username!r}'s password will not be sent in the "
            f"clear. Use a relay that offers STARTTLS, or configure the channel "
            f"without credentials."
        )
