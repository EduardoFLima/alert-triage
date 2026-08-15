"""Both channels against real servers in this process — real I/O, no external service.

The unit tests drive rendering and every failure path against fakes. What is
left to prove is that the wire format each adapter produces is one a real
server on the other end of a real socket accepts, which is exactly the part a
fake cannot answer for.
"""

import asyncio
import email
import json
import socket
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import Message
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, Envelope, Session

from alert_triage.adapters.email import EmailNotifier, EmailSettings
from alert_triage.adapters.teams import TeamsNotifier
from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident
from alert_triage.domain.report import TriageReport
from alert_triage.ports.notifier import NotifierError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _report() -> TriageReport:
    return TriageReport(
        incident=Incident(
            id="incident-1",
            service="checkout",
            alerts=(Alert(service="checkout", fired_at=NOON, source_id="a"),),
        ),
        subject="checkout is failing",
        body="Two alerts in thirty minutes.",
    )


class _Collector:
    """An SMTP handler that keeps what a real client actually submitted."""

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


def _free_port() -> int:
    """Ask the OS for a port nothing is listening on, and let it go again."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def smtp_server() -> Iterator[tuple[_Collector, int]]:
    """A real SMTP server on a loopback port, torn down with the test."""
    collector = _Collector()
    # The controller verifies startup by connecting to the port it was given,
    # so it cannot be handed 0 and asked to discover one.
    port = _free_port()
    controller = Controller(collector, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        yield collector, port
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
    smtp_server: tuple[_Collector, int],
) -> None:
    collector, port = smtp_server

    EmailNotifier(_settings(port)).deliver(_report())

    delivered = collector.messages[0]
    body = delivered.get_payload()
    assert delivered["Subject"] == "checkout is failing"
    assert isinstance(body, str)
    assert body.strip() == "Two alerts in thirty minutes."
    assert collector.recipients[0] == ["sre@example.com", "oncall@example.com"]


def test_a_relay_that_is_not_listening_is_a_delivery_failure() -> None:
    """Nothing is bound to the port, so this is a real connection refusal."""
    with pytest.raises(NotifierError):
        EmailNotifier(_settings(port=_free_port())).deliver(_report())


@dataclass
class _Webhook:
    """A real HTTP destination, and what a real client posted to it."""

    url: str
    posted: list[dict[str, Any]] = field(default_factory=list)
    status: int = 202


class _WebhookHandler(BaseHTTPRequestHandler):
    """Answers as a Workflows webhook does, recording what it was sent."""

    webhook: ClassVar[_Webhook]

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        self.webhook.posted.append(
            {
                "path": self.path,
                "content_type": self.headers["Content-Type"],
                "envelope": json.loads(body.decode("utf-8")),
            }
        )
        self.send_response(self.webhook.status)
        self.end_headers()
        self.wfile.write(
            b"" if self.webhook.status < 300 else b"flow rejected the card"
        )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Keep the test output free of the server's own access log."""


@pytest.fixture
def webhook() -> Iterator[_Webhook]:
    """A real HTTP server standing in for the webhook, on a loopback port."""
    server = HTTPServer(("127.0.0.1", 0), _WebhookHandler)
    destination = _Webhook(url=f"http://127.0.0.1:{server.server_port}/workflows/abc")
    _WebhookHandler.webhook = destination
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield destination
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_the_card_posted_over_a_real_socket_arrives_as_the_envelope_teams_expects(
    webhook: _Webhook,
) -> None:
    TeamsNotifier(webhook.url).deliver(_report())

    posted = webhook.posted[0]
    assert posted["path"] == "/workflows/abc"
    assert posted["content_type"] == "application/json"
    assert posted["envelope"]["type"] == "message"
    attachment = posted["envelope"]["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert [block["text"] for block in attachment["content"]["body"]] == [
        "checkout is failing",
        "Two alerts in thirty minutes.",
    ]


def test_a_webhook_that_rejects_the_card_is_a_delivery_failure_carrying_its_answer(
    webhook: _Webhook,
) -> None:
    webhook.status = 400

    with pytest.raises(NotifierError) as raised:
        TeamsNotifier(webhook.url).deliver(_report())

    assert "400" in str(raised.value)
    assert "flow rejected the card" in str(raised.value)


def test_the_adapters_need_no_event_loop_of_their_own() -> None:
    """Both channels are synchronous; only the test's SMTP server needs a loop."""
    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()
