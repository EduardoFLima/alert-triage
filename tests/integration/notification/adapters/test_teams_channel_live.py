import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

import pytest

from alert_triage.notification.adapters.teams import TeamsNotifier
from alert_triage.notification.contract import TriageReport
from alert_triage.notification.ports.notifier import NotifierError


@dataclass
class _Webhook:
    url: str
    posted: list[dict[str, Any]] = field(default_factory=list)
    status: int = 202


class _WebhookHandler(BaseHTTPRequestHandler):
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
        pass


@pytest.fixture
def webhook() -> Iterator[_Webhook]:
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
    with pytest.raises(NotifierError):
        TeamsNotifier(f"http://127.0.0.1:{free_port}/workflows/abc").deliver(report)
