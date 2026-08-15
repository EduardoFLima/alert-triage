import importlib
import re
import smtplib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from types import TracebackType

import pytest

from alert_triage.adapters.email import EmailNotifier, EmailSettings, render
from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident
from alert_triage.domain.report import TriageReport
from alert_triage.ports.notifier import Notifier, NotifierError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _report(
    subject: str = "checkout is failing", body: str = "Two alerts in thirty minutes."
) -> TriageReport:
    return TriageReport(
        incident=Incident(
            id="incident-1",
            service="checkout",
            alerts=(Alert(service="checkout", fired_at=NOON, source_id="a"),),
        ),
        subject=subject,
        body=body,
    )


def _settings(
    recipients: tuple[str, ...] = ("sre@example.com",),
    username: str | None = None,
    password: str | None = None,
) -> EmailSettings:
    return EmailSettings(
        host="smtp.example.com",
        port=587,
        sender="triage@example.com",
        recipients=recipients,
        username=username,
        password=password,
    )


def test_the_message_carries_the_report_s_subject_and_body() -> None:
    message = render(_report(), _settings())

    assert message["Subject"] == "checkout is failing"
    assert message.get_content().rstrip("\n") == "Two alerts in thirty minutes."


def test_the_message_is_addressed_from_the_sender_to_every_recipient() -> None:
    message = render(
        _report(), _settings(recipients=("sre@example.com", "oncall@example.com"))
    )

    assert message["From"] == "triage@example.com"
    assert message["To"] == "sre@example.com, oncall@example.com"


def test_the_message_is_plain_text_because_the_body_is() -> None:
    """The report carries no formatting, so the mail claims none."""
    message = render(_report(), _settings())

    assert message.get_content_type() == "text/plain"


def test_the_body_survives_characters_a_richer_medium_would_escape() -> None:
    body = 'Latency > 2s & rising: {"p99": 4.1}'

    message = render(_report(body=body), _settings())

    assert body in message.get_content()


def test_the_adapter_builds_the_standard_library_s_message_type() -> None:
    """The package is named ``email``; the message type must be the stdlib's."""
    assert isinstance(render(_report(), _settings()), EmailMessage)


def test_the_adapter_imports_the_standard_library_email_not_its_own_package() -> None:
    """Absolute imports save this, and a relative import would break it silently."""
    notifier = importlib.import_module("alert_triage.adapters.email.notifier")

    assert notifier.EmailMessage.__module__ == "email.message"
    assert notifier.EmailMessage is EmailMessage


@dataclass
class FakeSmtp:
    """A submission server that records what it was asked to do, and no socket."""

    fail_on: str | None = None
    failure: Exception = field(default_factory=lambda: smtplib.SMTPException("refused"))
    started_tls: bool = False
    logins: list[tuple[str, str]] = field(default_factory=list)
    sent: list[EmailMessage] = field(default_factory=list)
    closed: bool = False

    def __call__(self) -> "FakeSmtp":
        """Stand in for the factory the notifier opens a connection through."""
        return self

    def __enter__(self) -> "FakeSmtp":
        """Hand back the connection the notifier submits over."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Record that the notifier released the connection."""
        self.closed = True

    def starttls(self) -> None:
        """Secure the connection, or fail as a relay without STARTTLS does."""
        self._maybe_fail("starttls")
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        """Record the credentials the notifier authenticated with."""
        self._maybe_fail("login")
        self.logins.append((username, password))

    def send_message(self, message: EmailMessage) -> None:
        """Accept the message, as a relay that is working would."""
        self._maybe_fail("send_message")
        self.sent.append(message)

    def _maybe_fail(self, step: str) -> None:
        if self.fail_on == step:
            raise self.failure


def test_the_email_channel_satisfies_the_notifier_port() -> None:
    notifier: Notifier = EmailNotifier(_settings(), smtp=FakeSmtp())

    assert isinstance(notifier, Notifier)


def test_delivering_submits_the_rendered_message() -> None:
    smtp = FakeSmtp()

    EmailNotifier(_settings(), smtp=smtp).deliver(_report())

    assert [message["Subject"] for message in smtp.sent] == ["checkout is failing"]
    assert smtp.sent[0]["To"] == "sre@example.com"


def test_the_connection_is_secured_before_the_message_is_handed_over() -> None:
    smtp = FakeSmtp()

    EmailNotifier(_settings(), smtp=smtp).deliver(_report())

    assert smtp.started_tls


def test_credentials_are_used_when_the_relay_was_configured_with_them() -> None:
    smtp = FakeSmtp()

    EmailNotifier(_settings(username="triage", password="s3cret"), smtp=smtp).deliver(
        _report()
    )

    assert smtp.logins == [("triage", "s3cret")]


def test_an_unauthenticated_relay_is_not_logged_into() -> None:
    smtp = FakeSmtp()

    EmailNotifier(_settings(), smtp=smtp).deliver(_report())

    assert smtp.logins == []


def test_the_connection_is_released_once_the_report_is_delivered() -> None:
    smtp = FakeSmtp()

    EmailNotifier(_settings(), smtp=smtp).deliver(_report())

    assert smtp.closed


def test_a_refused_message_is_a_delivery_failure_naming_what_was_refused() -> None:
    smtp = FakeSmtp(
        fail_on="send_message",
        failure=smtplib.SMTPRecipientsRefused(
            {"sre@example.com": (550, b"no such user")}
        ),
    )

    with pytest.raises(NotifierError, match=re.escape("sre@example.com")):
        EmailNotifier(_settings(), smtp=smtp).deliver(_report())


def test_an_unreachable_server_is_a_delivery_failure_not_a_quiet_return() -> None:
    smtp = FakeSmtp(fail_on="starttls", failure=OSError("connection refused"))

    with pytest.raises(NotifierError, match=re.escape("smtp.example.com")):
        EmailNotifier(_settings(), smtp=smtp).deliver(_report())


def test_a_relay_that_does_not_offer_starttls_still_receives_the_report() -> None:
    """A plain local relay is a deployment this project explicitly anticipates."""
    smtp = FakeSmtp(
        fail_on="starttls", failure=smtplib.SMTPNotSupportedError("no STARTTLS")
    )

    EmailNotifier(_settings(), smtp=smtp).deliver(_report())

    assert len(smtp.sent) == 1
    assert not smtp.started_tls


def test_a_password_is_never_sent_over_a_connection_that_stayed_in_the_clear() -> None:
    """Secrecy is required exactly when there is a secret to keep."""
    smtp = FakeSmtp(
        fail_on="starttls", failure=smtplib.SMTPNotSupportedError("no STARTTLS")
    )

    with pytest.raises(NotifierError, match="STARTTLS"):
        EmailNotifier(
            _settings(username="triage", password="s3cret"), smtp=smtp
        ).deliver(_report())

    assert smtp.logins == []
    assert smtp.sent == []


def test_a_delivery_failure_names_the_incident_it_concerns() -> None:
    smtp = FakeSmtp(fail_on="send_message")

    with pytest.raises(NotifierError, match="incident-1"):
        EmailNotifier(_settings(), smtp=smtp).deliver(_report())
