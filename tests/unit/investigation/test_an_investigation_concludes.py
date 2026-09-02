"""What an investigation is entitled to say, and what it may say it on.

The conclusion is the thing this context newly produces, and the thing most
worth constraining: a hypothesis is the most quotable output the system has and
the least checkable. So it is kept only where findings survived to bear it.
"""

import pytest

from alert_triage.investigation.contract import (
    Confidence,
    Diagnosis,
    EvidenceItem,
    Finding,
    Findings,
    Signal,
)


def _finding(observation: str = "OOMKilled recurs") -> Finding:
    return Finding(
        signal=Signal.LOGS,
        observation=observation,
        occurrences=3,
        examples=(
            EvidenceItem(
                id="call-1/item-1", instant=None, summary="OOMKilled", payload={}
            ),
        ),
    )


def _findings(
    *found: Finding, consulted: tuple[Signal, ...] = (Signal.LOGS,)
) -> Findings:
    return Findings(findings=found, consulted=consulted)


def test_findings_record_the_signals_that_were_consulted() -> None:
    findings = _findings(_finding(), consulted=(Signal.LOGS, Signal.APM))

    assert findings.consulted == (Signal.LOGS, Signal.APM)


def test_findings_consulted_nothing_by_default() -> None:
    """Empty is not "every signal": it is the honest starting point."""
    assert Findings().consulted == ()


def test_consulting_nothing_is_distinguishable_from_consulting_everything() -> None:
    every = tuple(Signal)

    assert Findings(consulted=()).consulted != Findings(consulted=every).consulted


def test_a_declared_confidence_level_is_one_of_the_declared_set() -> None:
    assert Confidence("high") is Confidence.HIGH
    with pytest.raises(ValueError):
        Confidence("fairly sure")


def test_a_diagnosis_carries_the_conclusion_and_what_it_was_drawn_from() -> None:
    diagnosis = Diagnosis(
        headline="checkout is out of memory",
        account="The pods are being OOMKilled.",
        hypothesis="The container memory limit is too low for the current load.",
        confidence=Confidence.HIGH,
        findings=_findings(_finding()),
    )

    assert diagnosis.hypothesis is not None
    assert diagnosis.confidence is Confidence.HIGH
    assert diagnosis.findings.findings[0].observation == "OOMKilled recurs"


def test_a_headline_spanning_more_than_one_line_is_refused() -> None:
    """A channel presents it as a subject, which is one line or it is broken."""
    with pytest.raises(ValueError, match="single line"):
        Diagnosis(
            headline="checkout is out of memory\nand has been for an hour",
            account="...",
            hypothesis=None,
            confidence=None,
            findings=_findings(),
        )


def test_a_diagnosis_with_no_surviving_finding_carries_no_hypothesis() -> None:
    """A conclusion with nothing beneath it is the verdict this system withholds."""
    diagnosis = Diagnosis(
        headline="checkout alerted",
        account="Nothing survived the evidence check.",
        hypothesis="The database is overloaded.",
        confidence=Confidence.HIGH,
        findings=_findings(consulted=(Signal.LOGS,)),
    )

    assert diagnosis.hypothesis is None
    assert diagnosis.confidence is None


def test_a_diagnosis_keeps_its_hypothesis_where_a_finding_bears_it() -> None:
    diagnosis = Diagnosis(
        headline="checkout is out of memory",
        account="The pods are being OOMKilled.",
        hypothesis="The container memory limit is too low.",
        confidence=Confidence.LOW,
        findings=_findings(_finding()),
    )

    assert diagnosis.hypothesis == "The container memory limit is too low."
    assert diagnosis.confidence is Confidence.LOW
