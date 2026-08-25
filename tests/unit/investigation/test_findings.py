from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.investigation.contract import (
    MAX_EXAMPLES_PER_FINDING,
    EvidenceItem,
    Finding,
    Findings,
    Signal,
)

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def _item(offset: timedelta = timedelta(), summary: str = "OOMKilled") -> EvidenceItem:
    return EvidenceItem(
        id="call-1/item-1",
        instant=NOON + offset,
        summary=summary,
        payload={"message": summary},
    )


def test_an_evidence_item_carries_what_a_human_needs_to_recognise_it() -> None:
    item = _item()

    assert item.id == "call-1/item-1"
    assert item.instant == NOON
    assert item.summary == "OOMKilled"


def test_an_evidence_item_keeps_the_payload_the_platform_returned() -> None:
    """A summary is for reading; the payload is what was actually retrieved."""
    payload = {"message": "OOMKilled", "attributes": {"pod": "checkout-7f"}}

    item = EvidenceItem(
        id="call-1/item-1", instant=NOON, summary="OOMKilled", payload=payload
    )

    assert item.payload == payload


def test_an_evidence_item_without_a_summary_evidences_nothing() -> None:
    with pytest.raises(ValueError, match="summary"):
        EvidenceItem(id="call-1/item-1", instant=NOON, summary="   ", payload={})


def test_an_evidence_item_carries_the_address_of_the_thing_itself() -> None:
    """A reader who wants to see the evidence goes where the item says."""
    item = EvidenceItem(
        id="call-1/item-1",
        instant=NOON,
        summary="OOMKilled",
        payload={"message": "OOMKilled"},
        url="https://app.datadoghq.com/logs?event=AAAA",
    )

    assert item.url == "https://app.datadoghq.com/logs?event=AAAA"


def test_an_evidence_item_the_platform_cannot_address_has_no_url() -> None:
    """No address is a complete answer: evidence without one is still evidence."""
    assert _item().url is None


def test_an_evidence_item_may_have_no_instant() -> None:
    """An aggregate concerns a window rather than a moment; it is still evidence."""
    item = EvidenceItem(
        id="call-1", instant=None, summary="a flame graph", payload={"spans": []}
    )

    assert item.instant is None


def test_a_finding_carries_its_signal_observation_count_and_examples() -> None:
    item = _item()

    finding = Finding(
        signal=Signal.LOGS,
        observation="OOMKilled recurs every 40s",
        occurrences=47,
        examples=(item,),
    )

    assert finding.signal is Signal.LOGS
    assert finding.observation == "OOMKilled recurs every 40s"
    assert finding.occurrences == 47
    assert finding.examples == (item,)


def test_a_finding_cannot_claim_something_it_shows_nothing_for() -> None:
    """Evidence is what separates a finding from an assertion."""
    with pytest.raises(ValueError, match="example"):
        Finding(
            signal=Signal.LOGS,
            observation="the database is on fire",
            occurrences=1,
            examples=(),
        )


def test_a_finding_needs_an_observation_to_be_about_anything() -> None:
    with pytest.raises(ValueError, match="observation"):
        Finding(
            signal=Signal.LOGS, observation="  ", occurrences=1, examples=(_item(),)
        )


def test_a_finding_cannot_have_seen_less_than_it_shows() -> None:
    """An occurrence count below the examples is a contradiction, not a detail."""
    with pytest.raises(ValueError, match="occurrences"):
        Finding(
            signal=Signal.LOGS,
            observation="OOMKilled",
            occurrences=1,
            examples=(_item(), _item(timedelta(seconds=40))),
        )


def test_a_finding_keeps_a_bounded_number_of_examples() -> None:
    many = tuple(
        _item(timedelta(seconds=n)) for n in range(MAX_EXAMPLES_PER_FINDING + 5)
    )

    finding = Finding(
        signal=Signal.LOGS,
        observation="OOMKilled recurs",
        occurrences=len(many),
        examples=many,
    )

    assert len(finding.examples) == MAX_EXAMPLES_PER_FINDING
    assert finding.examples == many[:MAX_EXAMPLES_PER_FINDING]


def test_capping_the_examples_leaves_the_occurrence_count_alone() -> None:
    """How often it happened and how much of it we show are different facts."""
    many = tuple(_item(timedelta(seconds=n)) for n in range(400))

    finding = Finding(
        signal=Signal.LOGS, observation="OOMKilled", occurrences=400, examples=many
    )

    assert finding.occurrences == 400
    assert len(finding.examples) == MAX_EXAMPLES_PER_FINDING


def _finding(observation: str = "OOMKilled recurs") -> Finding:
    return Finding(
        signal=Signal.LOGS,
        observation=observation,
        occurrences=1,
        examples=(_item(),),
    )


def test_findings_carry_what_was_found() -> None:
    found = _finding()

    assert Findings(findings=(found,)).findings == (found,)


def test_findings_with_nothing_in_them_are_a_valid_result() -> None:
    """An investigation that ran and found nothing notable is not a failure."""
    nothing = Findings(findings=())

    assert nothing.findings == ()
    assert not nothing.anything_notable


def test_findings_with_something_in_them_say_so() -> None:
    assert Findings(findings=(_finding(),)).anything_notable


def test_findings_default_to_empty() -> None:
    assert Findings().findings == ()


def test_findings_that_gathered_everything_are_complete() -> None:
    assert Findings(findings=(_finding(),)).complete
    assert Findings().complete


def test_findings_carrying_a_retrieval_failure_are_incomplete() -> None:
    """Could not see all of it is not the same news as looked and it was clean."""
    findings = Findings(
        findings=(_finding(),), retrieval_failures=("the metrics search was refused",)
    )

    assert not findings.complete
    assert findings.retrieval_failures == ("the metrics search was refused",)


def test_incompleteness_is_independent_of_whether_anything_was_found() -> None:
    incomplete = Findings(retrieval_failures=("the log search was refused",))

    assert not incomplete.complete
    assert not incomplete.anything_notable


def test_retrieval_failures_default_to_none_at_all() -> None:
    assert Findings().retrieval_failures == ()
