"""What the model may cite is exactly what the platform was seen to return.

Every tool result passes through ``Retrieved`` on its way to the model, which
keeps it and hands back the identifiers it may be cited by. A failed retrieval
is recorded and refused rather than kept, because it evidences nothing.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.evidence import RETRIEVAL_FAILED, findings_from

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _logs(*messages: str, offset: timedelta = timedelta()) -> dict[str, Any]:
    return {
        "logs": [
            {"timestamp": (NOON + offset).isoformat(), "message": message}
            for message in messages
        ]
    }


def _aggregate() -> dict[str, Any]:
    return {"flame_graph": {"root": "checkout.handler", "self_time_ms": 4200}}


def _cited(
    cites: list[str], observation: str = "OOMKilled recurs", occurrences: int = 5
) -> dict[str, object]:
    return {"observation": observation, "occurrences": occurrences, "cites": cites}


def test_a_retained_result_is_citable_as_the_call_it_came_from() -> None:
    retrieved = Retrieved()

    offered = retrieved.retain(_aggregate())

    assert offered["call"] == "call-1"
    assert retrieved.resolve("call-1") is not None


def test_two_calls_in_one_investigation_get_distinct_identifiers() -> None:
    retrieved = Retrieved()

    first = retrieved.retain(_logs("first"))
    second = retrieved.retain(_logs("second"))

    assert first["call"] != second["call"]
    assert [
        call.summary
        for call in (retrieved.resolve("call-1"), retrieved.resolve("call-2"))
        if call
    ] != []


def test_a_retained_result_keeps_what_the_platform_returned_verbatim() -> None:
    retrieved = Retrieved()
    result = _aggregate()

    retrieved.retain(result)

    call = retrieved.resolve("call-1")
    assert call is not None and call.payload == result


def test_the_items_within_a_call_are_addressable_beneath_it() -> None:
    retrieved = Retrieved()

    offered = retrieved.retain(_logs("first", "second"))

    assert [item["id"] for item in offered["items"]] == [
        "call-1/item-1",
        "call-1/item-2",
    ]


def test_the_identifiers_the_model_is_shown_are_the_ones_that_resolve() -> None:
    retrieved = Retrieved()

    offered = retrieved.retain(_logs("first", "second"))

    for item in offered["items"]:
        assert retrieved.resolve(item["id"]) is not None


def test_a_citation_to_a_call_that_was_never_made_resolves_to_nothing() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("first"))

    assert retrieved.resolve("call-9") is None
    assert retrieved.resolve("call-1/item-9") is None


def test_each_investigation_starts_with_nothing_citable() -> None:
    """An identifier from an earlier incident must not resolve in a later one."""
    earlier = Retrieved()
    earlier.retain(_logs("first"))

    later = Retrieved()

    assert later.resolve("call-1") is None
    assert findings_from([_cited(["call-1"])], later, Signal.LOGS).findings == ()


def test_a_refused_retrieval_is_recorded_and_replaced_with_a_refusal() -> None:
    retrieved = Retrieved()

    refusal = retrieved.refuse("the platform refused the log search")

    assert RETRIEVAL_FAILED in str(refusal)
    assert retrieved.failures == ("the platform refused the log search",)


def test_a_refused_retrieval_is_not_citable_as_evidence() -> None:
    """A failure evidences nothing, however the model chooses to read it."""
    retrieved = Retrieved()
    retrieved.refuse("the platform refused the log search")

    assert retrieved.resolve("call-1") is None
    assert findings_from([_cited(["call-1"])], retrieved, Signal.LOGS).findings == ()


def test_failures_and_successes_accumulate_side_by_side() -> None:
    retrieved = Retrieved()

    retrieved.retain(_logs("first"))
    retrieved.refuse("the metrics search was refused")
    retrieved.retain(_logs("second"))

    assert retrieved.failures == ("the metrics search was refused",)
    assert retrieved.retrievals == 2
    assert retrieved.resolve("call-1") is not None
    assert retrieved.resolve("call-2") is not None
