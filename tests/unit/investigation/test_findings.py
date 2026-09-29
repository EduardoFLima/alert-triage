from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.investigation.contract import (
    MAX_EXAMPLES_PER_FINDING,
    EvidenceItem,
    Finding,
    Findings,
    Section,
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
    payload = {"message": "OOMKilled", "attributes": {"pod": "checkout-7f"}}

    item = EvidenceItem(
        id="call-1/item-1", instant=NOON, summary="OOMKilled", payload=payload
    )

    assert item.payload == payload


def test_an_evidence_item_without_a_summary_evidences_nothing() -> None:
    with pytest.raises(ValueError, match="summary"):
        EvidenceItem(id="call-1/item-1", instant=NOON, summary="   ", payload={})


def test_an_evidence_item_carries_the_address_of_the_thing_itself() -> None:
    item = EvidenceItem(
        id="call-1/item-1",
        instant=NOON,
        summary="OOMKilled",
        payload={"message": "OOMKilled"},
        url="https://app.datadoghq.com/logs?event=AAAA",
    )

    assert item.url == "https://app.datadoghq.com/logs?event=AAAA"


def test_an_evidence_item_the_platform_cannot_address_has_no_url() -> None:
    assert _item().url is None


def test_an_evidence_item_may_have_no_instant() -> None:
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
    with pytest.raises(ValueError, match="occurrences"):
        Finding(
            signal=Signal.LOGS,
            observation="OOMKilled",
            occurrences=1,
            examples=(_item(), _item(timedelta(seconds=40))),
        )


def test_a_finding_keeps_a_bounded_number_of_examples_but_counts_them_all() -> None:
    many = tuple(
        _item(timedelta(seconds=n)) for n in range(MAX_EXAMPLES_PER_FINDING + 5)
    )

    finding = Finding(
        signal=Signal.LOGS,
        observation="OOMKilled recurs",
        occurrences=400,
        examples=many,
    )

    assert len(finding.examples) == MAX_EXAMPLES_PER_FINDING
    assert finding.examples == many[:MAX_EXAMPLES_PER_FINDING]
    assert finding.occurrences == 400


def _finding(observation: str = "OOMKilled recurs") -> Finding:
    return Finding(
        signal=Signal.LOGS,
        observation=observation,
        occurrences=1,
        examples=(_item(),),
    )


def test_findings_with_something_in_them_are_notable_and_complete() -> None:
    found = _finding()
    findings = Findings(findings=(found,))

    assert findings.findings == (found,)
    assert findings.anything_notable
    assert findings.complete


def test_empty_findings_are_a_complete_result_with_nothing_notable() -> None:
    nothing = Findings()
    explicit = Findings(findings=())

    assert nothing.findings == ()
    assert explicit.findings == ()
    assert nothing.retrieval_failures == ()
    assert nothing.complete
    assert not nothing.anything_notable


def test_retrieval_failures_make_findings_incomplete_without_hiding_them() -> None:
    found = _finding()
    findings = Findings(
        findings=(found,), retrieval_failures=("the metrics search was refused",)
    )

    assert not findings.complete
    assert findings.retrieval_failures == ("the metrics search was refused",)
    assert findings.findings == (found,)
    assert findings.anything_notable


def test_incompleteness_is_independent_of_whether_anything_was_found() -> None:
    incomplete = Findings(retrieval_failures=("the log search was refused",))

    assert not incomplete.complete
    assert not incomplete.anything_notable


def test_every_signal_a_specialist_reports_under_is_named() -> None:
    assert {signal.value for signal in Signal} == {
        "logs",
        "apm",
        "trace",
        "infrastructure",
    }


def test_a_finding_names_the_signal_it_was_drawn_from() -> None:
    for signal in Signal:
        finding = Finding(
            signal=signal,
            observation="something moved",
            occurrences=1,
            examples=(_item(),),
        )

        assert finding.signal is signal


def test_a_finding_names_no_section_unless_it_is_given_one() -> None:
    unsectioned = Finding(
        signal=Signal.INFRASTRUCTURE,
        observation="checkout was rolled out",
        occurrences=1,
        examples=(_item(),),
    )
    sectioned = Finding(
        signal=Signal.INFRASTRUCTURE,
        observation="checkout was rolled out",
        occurrences=1,
        examples=(_item(),),
        section=Section.INFRASTRUCTURE,
    )

    assert unsectioned.section is None
    assert sectioned.section is Section.INFRASTRUCTURE


def test_a_section_is_drawn_from_a_closed_set() -> None:
    with pytest.raises(ValueError):
        Section("the bit with the graphs")
