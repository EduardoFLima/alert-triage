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

    offered = retrieved.retain_evidence(_aggregate())

    assert offered["call"] == "call-1"
    assert retrieved.resolve("call-1") is not None


def test_two_calls_in_one_investigation_get_distinct_identifiers() -> None:
    retrieved = Retrieved()

    first = retrieved.retain_evidence(_logs("first"))
    second = retrieved.retain_evidence(_logs("second"))

    assert first["call"] != second["call"]
    assert [
        call.summary
        for call in (retrieved.resolve("call-1"), retrieved.resolve("call-2"))
        if call
    ] != []


def test_a_retained_result_keeps_what_the_platform_returned_verbatim() -> None:
    retrieved = Retrieved()
    result = _aggregate()

    retrieved.retain_evidence(result)

    call = retrieved.resolve("call-1")
    assert call is not None and call.payload == result


def test_the_items_within_a_call_are_addressable_beneath_it() -> None:
    retrieved = Retrieved()

    offered = retrieved.retain_evidence(_logs("first", "second"))

    assert [item["id"] for item in offered["items"]] == [
        "call-1/item-1",
        "call-1/item-2",
    ]


def test_the_identifiers_the_model_is_shown_are_the_ones_that_resolve() -> None:
    retrieved = Retrieved()

    offered = retrieved.retain_evidence(_logs("first", "second"))

    for item in offered["items"]:
        assert retrieved.resolve(item["id"]) is not None


def test_a_citation_to_a_call_that_was_never_made_resolves_to_nothing() -> None:
    retrieved = Retrieved()
    retrieved.retain_evidence(_logs("first"))

    assert retrieved.resolve("call-9") is None
    assert retrieved.resolve("call-1/item-9") is None


def test_each_investigation_starts_with_nothing_citable() -> None:
    """An identifier from an earlier incident must not resolve in a later one."""
    earlier = Retrieved()
    earlier.retain_evidence(_logs("first"))

    later = Retrieved()

    assert later.resolve("call-1") is None
    assert findings_from([_cited(["call-1"])], later, Signal.LOGS).findings == ()


def test_a_refused_retrieval_is_recorded_and_replaced_with_a_refusal() -> None:
    retrieved = Retrieved()

    refusal = retrieved.refuse_evidence("the platform refused the log search")

    assert RETRIEVAL_FAILED in str(refusal)
    assert retrieved.failures == ("the platform refused the log search",)


def test_a_refused_retrieval_is_not_citable_as_evidence() -> None:
    """A failure evidences nothing, however the model chooses to read it."""
    retrieved = Retrieved()
    retrieved.refuse_evidence("the platform refused the log search")

    assert retrieved.resolve("call-1") is None
    assert findings_from([_cited(["call-1"])], retrieved, Signal.LOGS).findings == ()


def test_failures_and_successes_accumulate_side_by_side() -> None:
    retrieved = Retrieved()

    retrieved.retain_evidence(_logs("first"))
    retrieved.refuse_evidence("the metrics search was refused")
    retrieved.retain_evidence(_logs("second"))

    assert retrieved.failures == ("the metrics search was refused",)
    assert retrieved.retrievals == 2
    assert retrieved.resolve("call-1") is not None
    assert retrieved.resolve("call-2") is not None


class _Links:
    """A platform's addresses, standing in for the one bound to a real site.

    It ignores which tool produced the retrieval. Which product a tool opens is
    the platform adapter's decision and has tests of its own; what these
    establish is that an address, once built, reaches the evidence.
    """

    def to_retrieval(self, args: Any, *, tool: str) -> str | None:
        return f"https://platform/search?query={args.get('query', '')}"

    def to_item(self, payload: Any, within: str | None, *, tool: str) -> str | None:
        item = payload.get("id") if isinstance(payload, dict) else None
        return f"https://platform/logs?event={item}" if item else within


class _NamesTheTool:
    """A linker that reports which tool it was told produced the retrieval."""

    def to_retrieval(self, args: Any, *, tool: str) -> str | None:
        return f"https://platform/{tool}"

    def to_item(self, payload: Any, within: str | None, *, tool: str) -> str | None:
        return within


def test_the_tool_that_produced_a_retrieval_reaches_the_linker() -> None:
    """A platform serves its products on different pages; the tool says which."""
    retrieved = Retrieved(link=_NamesTheTool())

    retrieved.retain_evidence(_aggregate(), tool="get_datadog_metric")

    assert retrieved.resolve("call-1").url == (  # type: ignore[union-attr]
        "https://platform/get_datadog_metric"
    )


def _identified(*items: str) -> dict[str, Any]:
    return {
        "logs": [
            {"id": item, "timestamp": NOON.isoformat(), "message": item}
            for item in items
        ]
    }


def test_items_resolve_to_evidence_carrying_the_address_the_linker_built() -> None:
    retrieved = Retrieved(link=_Links())

    retrieved.retain_evidence(_identified("log-a", "log-b"))

    assert [retrieved.resolve(f"call-1/item-{n}").url for n in (1, 2)] == [  # type: ignore[union-attr]
        "https://platform/logs?event=log-a",
        "https://platform/logs?event=log-b",
    ]


def test_a_retrieval_kept_without_a_linker_addresses_nothing() -> None:
    """Evidence with no address is still evidence, which is what this describes."""
    retrieved = Retrieved()

    retrieved.retain_evidence(_logs("first"))

    assert retrieved.resolve("call-1/item-1").url is None  # type: ignore[union-attr]
    assert retrieved.resolve("call-1").url is None  # type: ignore[union-attr]


def test_an_item_the_platform_cannot_address_falls_back_to_its_retrieval() -> None:
    """A reader lands on the search that produced it rather than nowhere."""
    retrieved = Retrieved(link=_Links())

    retrieved.retain_evidence(_logs("first"), args={"query": "service:checkout"})

    assert retrieved.resolve("call-1/item-1").url == (  # type: ignore[union-attr]
        "https://platform/search?query=service:checkout"
    )


def test_the_call_an_aggregate_is_cited_by_carries_the_retrievals_address() -> None:
    """An aggregate has no item to point at, so the query is where to look."""
    retrieved = Retrieved(link=_Links())

    retrieved.retain_evidence(
        _aggregate(), args={"query": "service:checkout status:error"}
    )

    assert retrieved.resolve("call-1").url == (  # type: ignore[union-attr]
        "https://platform/search?query=service:checkout status:error"
    )


def test_a_retrieval_kept_with_no_arguments_is_still_addressed_as_it_can_be() -> None:
    """ADK hands over what the tool was called with; a caller need not."""
    retrieved = Retrieved(link=_Links())

    retrieved.retain_evidence(_aggregate())

    assert retrieved.resolve("call-1").url == "https://platform/search?query="  # type: ignore[union-attr]
