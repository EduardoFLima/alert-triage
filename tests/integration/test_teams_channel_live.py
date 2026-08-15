"""The Teams channel against a real HTTP server in this process.

The unit tests drive the card and every failure path against fakes. What is
left to prove is that the envelope arrives over a real socket as the shape
Workflows expects — the part a fake cannot answer for.
"""

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

import pytest

from alert_triage.adapters.teams import TeamsNotifier
from alert_triage.domain.report import TriageReport
from alert_triage.ports.notifier import NotifierError


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
    webhook: _Webhook, report: TriageReport
) -> None:
    TeamsNotifier(webhook.url).deliver(report)

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
    webhook: _Webhook, report: TriageReport
) -> None:
    webhook.status = 400

    with pytest.raises(NotifierError) as raised:
        TeamsNotifier(webhook.url).deliver(report)

    assert "400" in str(raised.value)
    assert "flow rejected the card" in str(raised.value)


def test_a_destination_that_is_not_listening_is_a_delivery_failure(
    free_port: int, report: TriageReport
) -> None:
    """Nothing is bound to the port, so this is a real connection refusal."""
    with pytest.raises(NotifierError):
        TeamsNotifier(f"http://127.0.0.1:{free_port}/workflows/abc").deliver(report)
