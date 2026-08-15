import io
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import Message
from types import TracebackType
from typing import Any

import pytest

from alert_triage.adapters.teams import (
    ADAPTIVE_CARD_CONTENT_TYPE,
    CARD_VERSION,
    TIMEOUT_SECONDS,
    TeamsNotifier,
    render,
)
from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident
from alert_triage.domain.report import TriageReport
from alert_triage.ports.notifier import Notifier, NotifierError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
WEBHOOK_URL = "https://prod-1.westeurope.logic.azure.com/workflows/abc/triggers/manual"


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
class FakeResponse:
    """What an opener hands back: a status and a body, and no socket."""

    status: int = 202
    body: bytes = b""

    def __enter__(self) -> "FakeResponse":
        """Hand back the response the notifier reads its status from."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the response, as a real one is released."""
        return None

    def read(self) -> bytes:
        """Answer the body the destination sent back."""
        return self.body


@dataclass
class FakeOpener:
    """An opener that records the request it was given, and never leaves the process."""

    response: FakeResponse = field(default_factory=FakeResponse)
    failure: Exception | None = None
    requests: list[urllib.request.Request] = field(default_factory=list)
    timeouts: list[float | None] = field(default_factory=list)

    def open(
        self, request: urllib.request.Request, timeout: float | None = None
    ) -> FakeResponse:
        """Record the request, then answer or fail as configured."""
        self.requests.append(request)
        self.timeouts.append(timeout)
        if self.failure is not None:
            raise self.failure
        return self.response


def _posted(opener: FakeOpener) -> dict[str, Any]:
    payload = opener.requests[0].data
    assert isinstance(payload, bytes)
    envelope: dict[str, Any] = json.loads(payload.decode("utf-8"))
    return envelope


def test_the_teams_channel_satisfies_the_notifier_port() -> None:
    notifier: Notifier = TeamsNotifier(WEBHOOK_URL, opener=FakeOpener())

    assert isinstance(notifier, Notifier)


def test_delivering_posts_the_rendered_card_to_the_configured_webhook() -> None:
    opener = FakeOpener()

    TeamsNotifier(WEBHOOK_URL, opener=opener).deliver(_report())

    assert opener.requests[0].full_url == WEBHOOK_URL
    assert opener.requests[0].get_method() == "POST"
    assert _posted(opener) == render(_report())


def test_the_post_announces_itself_as_json() -> None:
    opener = FakeOpener()

    TeamsNotifier(WEBHOOK_URL, opener=opener).deliver(_report())

    assert opener.requests[0].get_header("Content-type") == "application/json"


def test_the_post_is_bounded_so_a_hung_destination_cannot_hold_the_run_open() -> None:
    opener = FakeOpener()

    TeamsNotifier(WEBHOOK_URL, opener=opener).deliver(_report())

    assert opener.timeouts == [TIMEOUT_SECONDS]


@pytest.mark.parametrize("status", [200, 202, 204])
def test_any_success_status_is_taken_as_delivered(status: int) -> None:
    opener = FakeOpener(response=FakeResponse(status=status))

    TeamsNotifier(WEBHOOK_URL, opener=opener).deliver(_report())


def test_a_rejected_post_is_a_delivery_failure_carrying_status_and_body() -> None:
    """Workflows reports a malformed card as a 4xx with a body worth reading."""
    opener = FakeOpener(
        failure=urllib.error.HTTPError(
            url=WEBHOOK_URL,
            code=400,
            msg="Bad Request",
            hdrs=Message(),
            fp=io.BytesIO(b"Invalid card payload"),
        )
    )

    with pytest.raises(NotifierError) as raised:
        TeamsNotifier(WEBHOOK_URL, opener=opener).deliver(_report())

    assert "400" in str(raised.value)
    assert "Invalid card payload" in str(raised.value)


def test_a_non_success_status_answered_without_raising_is_still_a_failure() -> None:
    opener = FakeOpener(response=FakeResponse(status=500, body=b"flow is down"))

    with pytest.raises(NotifierError) as raised:
        TeamsNotifier(WEBHOOK_URL, opener=opener).deliver(_report())

    assert "500" in str(raised.value)
    assert "flow is down" in str(raised.value)


def test_an_unreachable_destination_is_a_delivery_failure_not_a_quiet_return() -> None:
    opener = FakeOpener(failure=urllib.error.URLError("name resolution failed"))

    with pytest.raises(NotifierError, match="name resolution failed"):
        TeamsNotifier(WEBHOOK_URL, opener=opener).deliver(_report())


def test_a_delivery_failure_names_the_incident_it_concerns() -> None:
    opener = FakeOpener(failure=urllib.error.URLError("down"))

    with pytest.raises(NotifierError, match="incident-1"):
        TeamsNotifier(WEBHOOK_URL, opener=opener).deliver(_report())


def test_a_rejection_whose_body_cannot_be_read_still_reports_why_it_failed() -> None:
    """A closed body stream must not turn a rejection into an unhandled error."""
    rejection = urllib.error.HTTPError(
        url=WEBHOOK_URL,
        code=502,
        msg="Bad Gateway",
        hdrs=Message(),
        fp=io.BytesIO(b"unreadable"),
    )
    rejection.close()

    with pytest.raises(NotifierError) as raised:
        TeamsNotifier(WEBHOOK_URL, opener=FakeOpener(failure=rejection)).deliver(
            _report()
        )

    assert "502" in str(raised.value)
    assert "Bad Gateway" in str(raised.value)
