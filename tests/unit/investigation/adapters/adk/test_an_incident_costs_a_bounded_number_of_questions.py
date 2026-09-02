"""How many questions one incident may cost, and what a refused one must say.

The bound is on questions, not on specialists. Going back to a specialist with
a narrower question is the manager's best move and the reason it holds the
thread at all; what has to be bounded is how much reasoning one incident buys,
which is a different quantity from how many specialists exist.
"""

from typing import Any

from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.consultation import (
    MAX_CONSULTATIONS,
    Consulted,
    bound_consultations_callback,
)
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.evidence import RETRIEVAL_FAILED
from alert_triage.investigation.domain.specialist import Specialist, Toolset


class _Reported(BaseModel):
    findings: list[dict[str, Any]] = []


def _specialist(name: str, signal: Signal) -> Specialist:
    return Specialist(
        name=name,
        signal=signal,
        instruction="Look.",
        output_schema=_Reported,
        toolsets=(Toolset(name="core", tools=("search_datadog_logs",)),),
    )


CREW = (
    _specialist("logs_specialist", Signal.LOGS),
    _specialist("apm_specialist", Signal.APM),
    _specialist("trace_specialist", Signal.TRACE),
    _specialist("infrastructure_specialist", Signal.INFRASTRUCTURE),
)


class _Tool:
    def __init__(self, name: str) -> None:
        self.name = name


def _consulted() -> Consulted:
    return Consulted(offered=CREW, retrieved=Retrieved())


def _ask(consulted: Consulted, name: str) -> dict[str, Any] | None:
    """One consultation, driven the way the framework drives one."""
    bound = bound_consultations_callback(consulted)
    refused = bound(tool=_Tool(name), args={"request": "look"}, tool_context=None)
    if refused is None:
        consulted.record(consulted.named(name), {"findings": []})  # type: ignore[arg-type]
    return refused


def test_asking_one_specialist_twice_spends_two_and_is_refused_neither() -> None:
    consulted = _consulted()

    first = _ask(consulted, "logs_specialist")
    second = _ask(consulted, "logs_specialist")

    assert (first, second) == (None, None)
    assert consulted.order == ("logs_specialist", "logs_specialist")


def test_a_consultation_beyond_the_bound_is_refused_and_nothing_is_run() -> None:
    consulted = _consulted()
    for _ in range(MAX_CONSULTATIONS):
        _ask(consulted, "logs_specialist")

    refused = _ask(consulted, "apm_specialist")

    assert refused is not None
    assert len(consulted.order) == MAX_CONSULTATIONS
    assert Signal.APM not in consulted.signals


def test_a_refusal_is_recorded() -> None:
    consulted = _consulted()
    for _ in range(MAX_CONSULTATIONS):
        _ask(consulted, "logs_specialist")

    _ask(consulted, "apm_specialist")

    assert len(consulted.refusals) == 1
    assert "apm_specialist" in consulted.refusals[0]


def test_a_refusal_says_the_consultation_did_not_happen() -> None:
    """A terse error is what a model reads as "that specialist found nothing"."""
    consulted = _consulted()
    for _ in range(MAX_CONSULTATIONS):
        _ask(consulted, "logs_specialist")

    refused = _ask(consulted, "apm_specialist")

    assert refused is not None
    assert refused["consultation_refused"] is True
    assert str(refused).find(RETRIEVAL_FAILED) == -1
    read_as = refused["read_this_as"]
    assert "did not happen" in read_as
    assert "not" in read_as and "nothing" in read_as


def test_every_declared_specialist_is_reachable_within_the_bound() -> None:
    consulted = _consulted()

    refusals = [_ask(consulted, specialist.name) for specialist in CREW]

    assert refusals == [None, None, None, None]
    assert consulted.signals == tuple(specialist.signal for specialist in CREW)


def test_the_bound_leaves_room_for_a_second_question_after_the_whole_crew() -> None:
    """A bound admitting each specialist once forbids the follow-up, not bounds it."""
    consulted = _consulted()
    for specialist in CREW:
        _ask(consulted, specialist.name)

    assert _ask(consulted, "logs_specialist") is None
    assert len(CREW) < MAX_CONSULTATIONS


def test_a_specialist_that_answered_unusably_does_not_end_the_investigation() -> None:
    """A specialist's bad turn is its own failure, not the investigation's.

    One agent writing prose where its schema was asked for must not cost every
    other agent's work.
    """
    from alert_triage.investigation.adapters.adk.consultation import (
        failed_consultation_callback,
    )

    consulted = _consulted()
    on_error = failed_consultation_callback(consulted)

    answer = on_error(
        tool=_Tool("logs_specialist"),
        args={"request": "look"},
        tool_context=None,
        error=ValueError("1 validation error for ReportedFindings"),
    )

    assert answer is not None
    assert answer["consultation_failed"] is True


def test_a_failed_consultation_reads_as_a_failure_not_as_a_quiet_specialist() -> None:
    from alert_triage.investigation.adapters.adk.consultation import (
        failed_consultation_callback,
    )

    consulted = _consulted()
    on_error = failed_consultation_callback(consulted)

    answer = on_error(
        tool=_Tool("logs_specialist"),
        args={},
        tool_context=None,
        error=ValueError("invalid json"),
    )

    assert answer is not None
    read_as = answer["read_this_as"]
    assert "did not answer" in read_as
    assert "not" in read_as and "nothing" in read_as


def test_a_failed_consultation_is_recorded_so_the_report_says_so() -> None:
    from alert_triage.investigation.adapters.adk.consultation import (
        failed_consultation_callback,
    )

    consulted = _consulted()
    on_error = failed_consultation_callback(consulted)

    on_error(
        tool=_Tool("logs_specialist"),
        args={},
        tool_context=None,
        error=ValueError("invalid json"),
    )

    assert len(consulted.refusals) == 1
    assert "logs_specialist" in consulted.refusals[0]


def test_an_error_from_something_that_is_not_a_specialist_is_left_to_raise() -> None:
    """A framework tool failing is not a consultation that went wrong."""
    from alert_triage.investigation.adapters.adk.consultation import (
        failed_consultation_callback,
    )

    consulted = _consulted()
    on_error = failed_consultation_callback(consulted)

    assert (
        on_error(
            tool=_Tool("set_model_response"),
            args={},
            tool_context=None,
            error=ValueError("boom"),
        )
        is None
    )
