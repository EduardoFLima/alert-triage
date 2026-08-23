from datetime import UTC, datetime, timedelta
from typing import Any

from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal
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


def test_a_finding_about_an_aggregate_keeps_the_call_as_its_evidence() -> None:
    retrieved = Retrieved()
    retrieved.retain(_aggregate())

    (finding,) = findings_from(
        [_cited(["call-1"], observation="one handler dominates")],
        retrieved,
        Signal.LOGS,
    ).findings

    (evidence,) = finding.examples
    assert evidence.id == "call-1"
    assert evidence.payload == _aggregate()


def test_a_pattern_finding_keeps_exactly_the_items_it_cited() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("first", "second", "third"))

    (finding,) = findings_from(
        [_cited(["call-1/item-1", "call-1/item-3"])], retrieved, Signal.LOGS
    ).findings

    assert [item.summary for item in finding.examples] == ["first", "third"]


def test_a_finding_names_the_signal_its_specialist_reports_under() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("first"))

    (finding,) = findings_from(
        [_cited(["call-1/item-1"])], retrieved, Signal.LOGS
    ).findings

    assert finding.signal is Signal.LOGS


def test_a_citation_to_a_call_that_was_never_made_resolves_to_nothing() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("first"))

    assert retrieved.resolve("call-9") is None
    assert retrieved.resolve("call-1/item-9") is None


def test_a_finding_citing_only_an_invented_identifier_is_discarded() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("first"))

    assert (
        findings_from([_cited(["call-1/item-9"])], retrieved, Signal.LOGS).findings
        == ()
    )


def test_a_finding_keeps_only_the_citations_that_resolve() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("real"))

    (finding,) = findings_from(
        [_cited(["call-1/item-1", "call-4/item-2"])], retrieved, Signal.LOGS
    ).findings

    assert [item.summary for item in finding.examples] == ["real"]


def test_a_fabricated_finding_does_not_take_its_siblings_with_it() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("real"))

    findings = findings_from(
        [
            _cited(["call-1/item-1"], observation="this one checks out"),
            _cited(["call-7"], observation="this one does not"),
        ],
        retrieved,
        Signal.LOGS,
    )

    assert [finding.observation for finding in findings.findings] == [
        "this one checks out"
    ]


def test_a_finding_citing_neither_grain_is_discarded() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("first"))

    assert findings_from([_cited([])], retrieved, Signal.LOGS).findings == ()


def test_a_payload_of_nothing_but_fabrications_is_empty_findings_not_an_error() -> None:
    """The investigation did run; it just said nothing that survived checking."""
    retrieved = Retrieved()
    retrieved.retain(_logs("first"))

    findings = findings_from(
        [_cited(["call-8"]), _cited(["call-9/item-1"])], retrieved, Signal.LOGS
    )

    assert findings.findings == ()
    assert not findings.anything_notable


def test_an_observation_with_nothing_to_say_is_discarded() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("first"))

    assert (
        findings_from(
            [_cited(["call-1/item-1"], observation="  ")], retrieved, Signal.LOGS
        ).findings
        == ()
    )


def test_an_occurrence_count_below_the_surviving_citations_is_raised_to_fit() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs("first", "second"))

    (finding,) = findings_from(
        [_cited(["call-1/item-1", "call-1/item-2"], occurrences=1)],
        retrieved,
        Signal.LOGS,
    ).findings

    assert finding.occurrences == 2


def test_more_citations_than_a_finding_shows_are_capped() -> None:
    retrieved = Retrieved()
    retrieved.retain(_logs(*(f"line {n}" for n in range(MAX_EXAMPLES_PER_FINDING + 5))))

    (finding,) = findings_from(
        [
            _cited(
                [f"call-1/item-{n}" for n in range(1, MAX_EXAMPLES_PER_FINDING + 6)],
                occurrences=400,
            )
        ],
        retrieved,
        Signal.LOGS,
    ).findings

    assert len(finding.examples) == MAX_EXAMPLES_PER_FINDING
    assert finding.occurrences == 400


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
