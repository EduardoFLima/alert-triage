import email
from collections.abc import Iterator
from email.message import Message
from typing import Any

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, Envelope, Session

from alert_triage.notification.adapters.email import EmailNotifier, EmailSettings
from alert_triage.notification.contract import TriageReport
from alert_triage.notification.ports.notifier import NotifierError


class _Collector:
    def __init__(self) -> None:
        self.messages: list[Message] = []
        self.recipients: list[list[str]] = []

    async def handle_DATA(  # noqa: N802 - aiosmtpd names the hook
        self, server: SMTP, session: Session, envelope: Envelope
    ) -> str:
        content = envelope.content
        assert isinstance(content, bytes)
        self.messages.append(email.message_from_bytes(content))
        self.recipients.append(list(envelope.rcpt_tos))
        return "250 OK"


@pytest.fixture
def smtp_server(free_port: int) -> Iterator[tuple[_Collector, int]]:
    collector = _Collector()
    controller = Controller(collector, hostname="127.0.0.1", port=free_port)
    controller.start()
    try:
        yield collector, free_port
    finally:
        controller.stop()


def _settings(port: int, **overrides: Any) -> EmailSettings:
    return EmailSettings(
        host="127.0.0.1",
        port=port,
        sender="triage@example.com",
        recipients=("sre@example.com", "oncall@example.com"),
        **overrides,
    )


def test_a_report_submitted_over_a_real_socket_arrives_intact(
    smtp_server: tuple[_Collector, int], report: TriageReport
) -> None:
    collector, port = smtp_server

    EmailNotifier(_settings(port)).deliver(report)

    delivered = collector.messages[0]
    body = delivered.get_payload()
    assert delivered["Subject"] == "checkout is failing"
    assert isinstance(body, str)
    assert body.strip() == "Two alerts in thirty minutes."
    assert collector.recipients[0] == ["sre@example.com", "oncall@example.com"]


def test_a_relay_that_is_not_listening_is_a_delivery_failure(
    free_port: int, report: TriageReport
) -> None:
    with pytest.raises(NotifierError):
        EmailNotifier(_settings(port=free_port)).deliver(report)
