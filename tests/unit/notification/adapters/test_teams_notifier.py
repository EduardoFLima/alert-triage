import io
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import Message
from typing import Any

import pytest

from alert_triage.notification.adapters.teams import (
    ADAPTIVE_CARD_CONTENT_TYPE,
    CARD_VERSION,
    TIMEOUT_SECONDS,
    TeamsNotifier,
    post_over_urllib,
    render,
)
from alert_triage.notification.contract import TriageReport
from alert_triage.notification.ports.notifier import Notifier, NotifierError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
WEBHOOK_URL = "https://prod-1.westeurope.logic.azure.com/workflows/abc/triggers/manual"


def _report(
    subject: str = "checkout is failing", body: str = "Two alerts in thirty minutes."
) -> TriageReport:
    return TriageReport(
        incident_id="incident-1",
        service="checkout",
        subject=subject,
        body=body,
    )


def _card(envelope: dict[str, Any]) -> dict[str, Any]:
    content: dict[str, Any] = envelope["attachments"][0]["content"]
    return content


def _text_blocks(envelope: dict[str, Any]) -> list[str]:
    return [block["text"] for block in _card(envelope)["body"]]


def test_the_envelope_is_the_message_shape_a_webhook_accepts() -> None:
    envelope = render(_report())

    assert envelope["type"] == "message"
    assert len(envelope["attachments"]) == 1
    assert envelope["attachments"][0]["contentType"] == ADAPTIVE_CARD_CONTENT_TYPE
    assert envelope["attachments"][0]["contentUrl"] is None


def test_the_attachment_is_an_adaptive_card_declaring_its_schema() -> None:
    card = _card(render(_report()))

    assert card["type"] == "AdaptiveCard"
    assert card["version"] == CARD_VERSION
    assert card["$schema"] == "http://adaptivecards.io/schemas/adaptive-card.json"


def test_the_subject_heads_the_card_and_the_body_follows_it() -> None:
    assert _text_blocks(render(_report())) == [
        "checkout is failing",
        "Two alerts in thirty minutes.",
    ]


def test_a_long_body_wraps_rather_than_being_cut_off() -> None:
    assert all(block["wrap"] for block in _card(render(_report()))["body"])


def test_the_body_is_carried_verbatim_however_a_richer_medium_would_escape_it() -> None:
    body = 'Latency > 2s & rising: {"p99": 4.1}'

    assert body in _text_blocks(render(_report(body=body)))


@dataclass
class FakePost:
    """A POST that never leaves the process, recording what it was asked to send."""

    status: int = 202
    answer: bytes = b""
    failure: Exception | None = None
    calls: list[tuple[str, bytes]] = field(default_factory=list)

    def __call__(self, url: str, body: bytes) -> tuple[int, bytes]:
        """Record the call, then answer or fail as configured."""
        self.calls.append((url, body))
        if self.failure is not None:
            raise self.failure
        return self.status, self.answer


def _sent(post: FakePost) -> dict[str, Any]:
    envelope: dict[str, Any] = json.loads(post.calls[0][1].decode("utf-8"))
    return envelope


def test_the_teams_channel_satisfies_the_notifier_port() -> None:
    notifier: Notifier = TeamsNotifier(WEBHOOK_URL, post=FakePost())

    assert isinstance(notifier, Notifier)


def test_delivering_posts_the_rendered_card_to_the_configured_webhook() -> None:
    post = FakePost()

    TeamsNotifier(WEBHOOK_URL, post=post).deliver(_report())

    assert post.calls[0][0] == WEBHOOK_URL
    assert _sent(post) == render(_report())


@pytest.mark.parametrize("status", [200, 202, 204])
def test_any_success_status_is_taken_as_delivered(status: int) -> None:
    TeamsNotifier(WEBHOOK_URL, post=FakePost(status=status)).deliver(_report())


def test_a_rejected_post_is_a_delivery_failure_carrying_status_and_body() -> None:
    """Workflows reports a malformed card as a 4xx with a body worth reading."""
    post = FakePost(status=400, answer=b"Invalid card payload")

    with pytest.raises(NotifierError) as raised:
        TeamsNotifier(WEBHOOK_URL, post=post).deliver(_report())

    assert "400" in str(raised.value)
    assert "Invalid card payload" in str(raised.value)


def test_a_body_the_destination_encoded_oddly_still_reaches_the_operator() -> None:
    post = FakePost(status=500, answer=b"\xff\xfeflow is down")

    with pytest.raises(NotifierError, match="flow is down"):
        TeamsNotifier(WEBHOOK_URL, post=post).deliver(_report())


def test_an_unreachable_destination_is_a_delivery_failure_not_a_quiet_return() -> None:
    post = FakePost(failure=urllib.error.URLError("name resolution failed"))

    with pytest.raises(NotifierError, match="name resolution failed"):
        TeamsNotifier(WEBHOOK_URL, post=post).deliver(_report())


def test_a_delivery_failure_names_the_incident_it_concerns() -> None:
    post = FakePost(failure=urllib.error.URLError("down"))

    with pytest.raises(NotifierError, match="incident-1"):
        TeamsNotifier(WEBHOOK_URL, post=post).deliver(_report())


@dataclass
class FakeUrlopen:
    """Stands in for urllib's own opener, so the request itself can be inspected."""

    rejection: urllib.error.HTTPError | None = None
    requests: list[urllib.request.Request] = field(default_factory=list)
    timeouts: list[float | None] = field(default_factory=list)

    def __call__(
        self, request: urllib.request.Request, timeout: float | None = None
    ) -> "FakeHttpResponse":
        """Record the request and its bound, then answer or reject."""
        self.requests.append(request)
        self.timeouts.append(timeout)
        if self.rejection is not None:
            raise self.rejection
        return FakeHttpResponse()


class FakeHttpResponse:
    """The little urllib answers back: a status and a body, and no socket."""

    status = 202

    def __enter__(self) -> "FakeHttpResponse":
        """Hand back the response, as urllib's own context manager does."""
        return self

    def __exit__(self, *exception: object) -> None:
        """Release the response."""

    def read(self) -> bytes:
        """Answer an accepted post's empty body."""
        return b""


def test_the_default_post_announces_itself_as_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urlopen = FakeUrlopen()
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    post_over_urllib(WEBHOOK_URL, b'{"type": "message"}')

    request = urlopen.requests[0]
    assert request.full_url == WEBHOOK_URL
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert request.data == b'{"type": "message"}'


def test_the_default_post_is_bounded_so_a_hung_destination_cannot_hold_a_run_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urlopen = FakeUrlopen()
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    post_over_urllib(WEBHOOK_URL, b"{}")

    assert urlopen.timeouts == [TIMEOUT_SECONDS]


def test_the_default_post_reads_a_rejection_rather_than_raising_it_onward(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The status and the explanation arrive together, and no stream is left open."""
    rejection = urllib.error.HTTPError(
        url=WEBHOOK_URL,
        code=400,
        msg="Bad Request",
        hdrs=Message(),
        fp=io.BytesIO(b"Invalid card payload"),
    )
    monkeypatch.setattr(urllib.request, "urlopen", FakeUrlopen(rejection=rejection))

    assert post_over_urllib(WEBHOOK_URL, b"{}") == (400, b"Invalid card payload")
