"""What a reader is shown beneath the prose, reproduced as it was retrieved.

These assertions moved here from triage when the report's body did. They are the
same assertions: an account states what was found, shows the records behind it,
says what it did and did not examine, and renders an address whole on a line of
its own. Where they live changed; what they establish did not.
"""

from datetime import UTC, datetime, timedelta

from alert_triage.investigation.contract import (
    Confidence,
    EvidenceItem,
    Finding,
    Findings,
    Signal,
)
from alert_triage.investigation.domain.account import (
    EVIDENCE_INCOMPLETE,
    NO_HYPOTHESIS,
    compose,
    without_words,
)

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
EVERY_SIGNAL = tuple(Signal)
LOG_LINK = "https://app.datadoghq.com/logs?query=service%3Acheckout&event=AQAAA"


def _item(
    offset: timedelta = timedelta(),
    summary: str = "OOMKilled",
    url: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        id="call-1/item-1",
        instant=NOON + offset,
        summary=summary,
        payload={"message": summary},
        url=url,
    )


def _finding(
    observation: str = "OOMKilled recurs every 40s",
    occurrences: int = 47,
    examples: tuple[EvidenceItem, ...] = (),
) -> Finding:
    return Finding(
        signal=Signal.LOGS,
        observation=observation,
        occurrences=occurrences,
        examples=examples or (_item(),),
    )


def _account(
    findings: Findings, narrative: str = "The pods keep dying under load."
) -> str:
    return compose(narrative, findings)


def _found(
    *findings: Finding, consulted: tuple[Signal, ...] = EVERY_SIGNAL
) -> Findings:
    return Findings(findings=findings, consulted=consulted)


def _evidence_lines(account: str) -> list[str]:
    """The indented lines beneath a finding, which is where evidence renders."""
    return [line.strip() for line in account.splitlines() if line.startswith("    ")]


def test_an_account_states_what_was_found() -> None:
    account = _account(_found(_finding(observation="OOMKilled recurs every 40s")))

    assert "OOMKilled recurs every 40s" in account


def test_an_account_carries_the_evidence_behind_each_finding() -> None:
    account = _account(
        _found(_finding(examples=(_item(summary="container OOMKilled"),)))
    )

    assert "container OOMKilled" in account
    assert NOON.isoformat() in account


def test_an_account_says_how_often_the_pattern_occurred() -> None:
    """The count is what survives when only a handful of records travel with it."""
    assert "47" in _account(_found(_finding(occurrences=47)))


def test_an_account_carries_what_the_agent_wrote_above_the_evidence() -> None:
    account = _account(_found(_finding()), narrative="The pods keep dying under load.")

    assert account.index("The pods keep dying under load.") < account.index("OOMKilled")


def test_an_investigation_that_found_nothing_notable_says_so() -> None:
    """Not an empty section: 'we looked and it is clean' is the news."""
    assert "nothing notable" in _account(_found()).lower()


def test_an_investigation_that_found_nothing_names_the_signals_it_consulted() -> None:
    """'Nothing notable' is only interpretable against the scope it covered."""
    account = _account(_found()).lower()

    for signal in EVERY_SIGNAL:
        assert signal.value in account


def test_an_account_claims_no_signal_that_was_not_consulted() -> None:
    account = _account(_found(consulted=(Signal.LOGS, Signal.TRACE))).lower()

    assert Signal.APM.value not in account
    assert Signal.INFRASTRUCTURE.value not in account


def test_the_account_of_what_was_examined_follows_what_was_consulted() -> None:
    """It tracks the investigation, not the crew a deployment happens to declare."""
    alone = _account(_found(consulted=(Signal.LOGS,)))
    whole = _account(_found(consulted=EVERY_SIGNAL))

    assert alone != whole
    assert Signal.INFRASTRUCTURE.value in whole.lower()
    assert Signal.INFRASTRUCTURE.value not in alone.lower()


def test_an_investigation_that_consulted_nobody_says_no_signal_was_examined() -> None:
    """Distinct from 'nothing notable': one looked, the other never did."""
    account = _account(_found(consulted=())).lower()

    assert "no signal was examined" in account


def test_an_account_reads_an_aggregate_with_no_instant() -> None:
    """A flame graph concerns a window, not a moment; it is still evidence."""
    aggregate = EvidenceItem(
        id="call-2",
        instant=None,
        summary="one handler holds 84% of the time",
        payload={},
    )

    assert "one handler holds 84% of the time" in _account(
        _found(_finding(examples=(aggregate,)))
    )


def test_an_investigation_that_could_not_see_everything_says_so() -> None:
    findings = Findings(
        findings=(_finding(observation="OOMKilled recurs every 40s"),),
        retrieval_failures=("the log aggregation was refused",),
        consulted=EVERY_SIGNAL,
    )

    account = _account(findings)

    assert EVIDENCE_INCOMPLETE in account
    assert "OOMKilled recurs every 40s" in account


def test_an_incomplete_investigation_that_found_nothing_still_says_so() -> None:
    """The dangerous account: nothing found, and part of the looking never happened."""
    findings = Findings(
        retrieval_failures=("the log search was refused",), consulted=EVERY_SIGNAL
    )

    assert EVIDENCE_INCOMPLETE in _account(findings)


def test_a_complete_investigation_carries_no_incompleteness_note() -> None:
    assert EVIDENCE_INCOMPLETE not in _account(_found(_finding()))
    assert EVIDENCE_INCOMPLETE not in _account(_found())


def test_evidence_carrying_an_address_renders_it_on_its_own_line() -> None:
    """A reader who wants to see the finding for themselves goes from here."""
    findings = _found(
        _finding(examples=(_item(summary="container OOMKilled", url=LOG_LINK),))
    )

    assert _evidence_lines(_account(findings)) == [
        f"{NOON.isoformat()} container OOMKilled",
        LOG_LINK,
    ]


def test_evidence_with_no_address_renders_exactly_as_it_did_before() -> None:
    """No address is a complete answer, and the account notes no absence."""
    findings = _found(_finding(examples=(_item(summary="OOMKilled"),)))

    assert _evidence_lines(_account(findings)) == [f"{NOON.isoformat()} OOMKilled"]


def test_an_address_is_rendered_whole_beside_a_summary_that_was_shortened() -> None:
    """The failure this exists to fix: half a URL still reads as a link."""
    shortened = f"{'word ' * 60}…"
    findings = _found(_finding(examples=(_item(summary=shortened, url=LOG_LINK),)))

    read, address = _evidence_lines(_account(findings))

    assert address == LOG_LINK
    assert read.endswith("…")
    assert LOG_LINK not in read


def test_an_aggregates_address_stands_on_a_line_of_its_own_too() -> None:
    """An item with no instant is an aggregate, and is still somewhere to go."""
    aggregate = EvidenceItem(
        id="call-1",
        instant=None,
        summary="4200 errors in the window",
        payload={"count": 4200},
        url=LOG_LINK,
    )

    assert _evidence_lines(_account(_found(_finding(examples=(aggregate,))))) == [
        "4200 errors in the window",
        LOG_LINK,
    ]


def test_a_composed_account_states_the_conclusion_and_its_confidence() -> None:
    account = without_words(
        "the container limit is too low", Confidence.HIGH, _found(_finding())
    )

    assert "the container limit is too low" in account
    assert Confidence.HIGH.value in account


def test_a_composed_account_says_plainly_when_there_was_no_hypothesis() -> None:
    account = without_words(None, None, _found(_finding()))

    assert NO_HYPOTHESIS in account
    assert "OOMKilled recurs every 40s" in account


def test_a_composed_account_shows_the_same_evidence_a_written_one_does() -> None:
    """The fallback is the renderer with nothing written above it, not other code."""
    findings = _found(_finding(examples=(_item(summary="container OOMKilled"),)))

    assert _evidence_lines(without_words(None, None, findings)) == _evidence_lines(
        _account(findings)
    )


def test_a_written_account_states_the_confidence_whatever_the_agent_wrote() -> None:
    """An instruction to state it is a request; a reader needs a guarantee."""
    account = compose(
        "The pods keep dying under load.", _found(_finding()), Confidence.MEDIUM
    )

    assert Confidence.MEDIUM.value in account


def test_the_stated_confidence_is_the_one_the_investigation_reached() -> None:
    low = compose("The pods keep dying.", _found(_finding()), Confidence.LOW)
    high = compose("The pods keep dying.", _found(_finding()), Confidence.HIGH)

    assert Confidence.LOW.value in low
    assert Confidence.HIGH.value not in low
    assert Confidence.HIGH.value in high


def test_an_account_with_no_confidence_states_none() -> None:
    """There was no hypothesis to weigh, and inventing a level would be worse."""
    account = compose("Nothing conclusive.", _found(_finding()), None)

    for level in Confidence:
        assert level.value not in account


def test_the_confidence_stands_between_the_prose_and_the_evidence() -> None:
    account = compose(
        "The pods keep dying under load.", _found(_finding()), Confidence.MEDIUM
    )

    assert (
        account.index("The pods keep dying under load.")
        < account.index(Confidence.MEDIUM.value)
        < account.index("OOMKilled recurs every 40s")
    )
