"""What survives the citation check, and what is dropped before anyone reads it.

Stated against whatever kept the evidence rather than against the adapter that
keeps it: the discipline is that a citation must resolve, and how a tool result
came to be keyed is not its business.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from alert_triage.investigation.contract import (
    MAX_EXAMPLES_PER_FINDING,
    EvidenceItem,
    Signal,
)
from alert_triage.investigation.domain.evidence import findings_from

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


class _Retained:
    """What one investigation was shown, keyed the way it was offered to cite it."""

    def __init__(self, evidence: dict[str, EvidenceItem]) -> None:
        self._evidence = evidence

    def resolve(self, citation: str) -> EvidenceItem | None:
        return self._evidence.get(citation)


def _retained(result: dict[str, Any]) -> _Retained:
    """One retrieval, citable whole as ``call-1`` and item by item beneath it."""
    items = result.get("logs", [])
    evidence = {
        "call-1": EvidenceItem(
            id="call-1", instant=None, summary=str(result), payload=result
        )
    }
    for position, item in enumerate(items, start=1):
        evidence[f"call-1/item-{position}"] = EvidenceItem(
            id=f"call-1/item-{position}",
            instant=NOON,
            summary=item["message"],
            payload=item,
        )
    return _Retained(evidence)


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


def test_a_finding_about_an_aggregate_keeps_the_call_as_its_evidence() -> None:
    retrieved = _retained(_aggregate())

    (finding,) = findings_from(
        [_cited(["call-1"], observation="one handler dominates")],
        retrieved,
        Signal.LOGS,
    ).findings

    (evidence,) = finding.examples
    assert evidence.id == "call-1"
    assert evidence.payload == _aggregate()


def test_a_pattern_finding_keeps_exactly_the_items_it_cited() -> None:
    retrieved = _retained(_logs("first", "second", "third"))

    (finding,) = findings_from(
        [_cited(["call-1/item-1", "call-1/item-3"])], retrieved, Signal.LOGS
    ).findings

    assert [item.summary for item in finding.examples] == ["first", "third"]


def test_a_finding_names_the_signal_its_specialist_reports_under() -> None:
    retrieved = _retained(_logs("first"))

    (finding,) = findings_from(
        [_cited(["call-1/item-1"])], retrieved, Signal.LOGS
    ).findings

    assert finding.signal is Signal.LOGS


def test_a_finding_citing_only_an_invented_identifier_is_discarded() -> None:
    retrieved = _retained(_logs("first"))

    assert (
        findings_from([_cited(["call-1/item-9"])], retrieved, Signal.LOGS).findings
        == ()
    )


def test_a_finding_keeps_only_the_citations_that_resolve() -> None:
    retrieved = _retained(_logs("real"))

    (finding,) = findings_from(
        [_cited(["call-1/item-1", "call-4/item-2"])], retrieved, Signal.LOGS
    ).findings

    assert [item.summary for item in finding.examples] == ["real"]


def test_a_fabricated_finding_does_not_take_its_siblings_with_it() -> None:
    retrieved = _retained(_logs("real"))

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
    retrieved = _retained(_logs("first"))

    assert findings_from([_cited([])], retrieved, Signal.LOGS).findings == ()


def test_a_payload_of_nothing_but_fabrications_is_empty_findings_not_an_error() -> None:
    """The investigation did run; it just said nothing that survived checking."""
    retrieved = _retained(_logs("first"))

    findings = findings_from(
        [_cited(["call-8"]), _cited(["call-9/item-1"])], retrieved, Signal.LOGS
    )

    assert findings.findings == ()
    assert not findings.anything_notable


def test_an_observation_with_nothing_to_say_is_discarded() -> None:
    retrieved = _retained(_logs("first"))

    assert (
        findings_from(
            [_cited(["call-1/item-1"], observation="  ")], retrieved, Signal.LOGS
        ).findings
        == ()
    )


def test_an_occurrence_count_below_the_surviving_citations_is_raised_to_fit() -> None:
    retrieved = _retained(_logs("first", "second"))

    (finding,) = findings_from(
        [_cited(["call-1/item-1", "call-1/item-2"], occurrences=1)],
        retrieved,
        Signal.LOGS,
    ).findings

    assert finding.occurrences == 2


def test_more_citations_than_a_finding_shows_are_capped() -> None:
    retrieved = _retained(
        _logs(*(f"line {n}" for n in range(MAX_EXAMPLES_PER_FINDING + 5)))
    )

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
