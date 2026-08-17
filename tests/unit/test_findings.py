from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.domain.findings import (
    MAX_EXAMPLES_PER_FINDING,
    Finding,
    Findings,
    LogRecord,
    Signal,
)

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def _record(offset: timedelta = timedelta(), message: str = "OOMKilled") -> LogRecord:
    return LogRecord(
        timestamp=NOON + offset,
        level="ERROR",
        message=message,
        service="checkout",
    )


def test_a_log_record_carries_what_identifies_the_line_to_a_human() -> None:
    record = _record()

    assert record.timestamp == NOON
    assert record.level == "ERROR"
    assert record.message == "OOMKilled"
    assert record.service == "checkout"


def test_a_log_record_needs_a_message_to_be_evidence_of_anything() -> None:
    with pytest.raises(ValueError, match="message"):
        LogRecord(timestamp=NOON, level="ERROR", message="   ", service="checkout")


def test_a_finding_carries_its_signal_observation_count_and_examples() -> None:
    record = _record()

    finding = Finding(
        signal=Signal.LOGS,
        observation="OOMKilled recurs every 40s",
        occurrences=47,
        examples=(record,),
    )

    assert finding.signal is Signal.LOGS
    assert finding.observation == "OOMKilled recurs every 40s"
    assert finding.occurrences == 47
    assert finding.examples == (record,)


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
            signal=Signal.LOGS, observation="  ", occurrences=1, examples=(_record(),)
        )


def test_a_finding_cannot_have_seen_less_than_it_shows() -> None:
    """An occurrence count below the examples is a contradiction, not a detail."""
    with pytest.raises(ValueError, match="occurrences"):
        Finding(
            signal=Signal.LOGS,
            observation="OOMKilled",
            occurrences=1,
            examples=(_record(), _record(timedelta(seconds=40))),
        )


def test_a_finding_keeps_a_bounded_number_of_examples() -> None:
    many = tuple(
        _record(timedelta(seconds=n)) for n in range(MAX_EXAMPLES_PER_FINDING + 5)
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
    many = tuple(_record(timedelta(seconds=n)) for n in range(400))

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
        examples=(_record(),),
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
