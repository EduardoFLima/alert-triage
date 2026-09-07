"""A bound that was reached is an account cut short, never one that came back clean.

An investigation stopped by a breaker is on the same footing as one whose
retrieval partly failed: what it holds is no less true for the bound having been
reached, and an incomplete automated triage is itself a reason a human should
look sooner. So it completes, its report is delivered, and it does not spend one
of the incident's attempts.

The exception is a trip that produced nothing at all. "We ran out of budget and
learned nothing" is not worth a message while there is still an attempt left to
learn something, so that raises and the incident is investigated again. It stays
deliberately distinct from a manager that *chose* to consult nobody, which is an
ordinary result: being stopped from asking and deciding not to ask are different
facts, and the refusal wording exists to keep them apart.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.consultation import (
    Consulted,
    bound_consultations_callback,
)
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.adk.investigator import AdkInvestigator
from alert_triage.investigation.contract import InvestigationTarget, Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset
from alert_triage.investigation.ports.investigator import InvestigatorError
from alert_triage.shared.window import Window

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


class _Reported(BaseModel):
    findings: list[dict[str, Any]] = []


def _specialist(name: str, signal: Signal) -> Specialist:
    return Specialist(
        name=name,
        signal=signal,
        instruction="Look.",
        output_schema=_Reported,
        toolsets=(
            Toolset(provider="datadog", name="core", tools=("search_datadog_logs",)),
        ),
    )


LOGS = _specialist("logs_specialist", Signal.LOGS)
APM = _specialist("apm_specialist", Signal.APM)


def _target() -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON + timedelta(minutes=20)),
        alert_count=1,
    )


def _tool(name: str) -> Any:
    return type("_T", (), {"name": name})()


def _finding() -> dict[str, Any]:
    return {
        "observation": "OOMKilled recurs",
        "occurrences": 3,
        "cites": ["call-1/item-1"],
    }


def _keeps_asking(*, gathers: bool) -> Any:
    """A manager that spends its budget and keeps going, with or without evidence."""

    def _run(
        crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        if gathers:
            retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
        bound = bound_consultations_callback(consulted)
        for _ in range(consulted.bounds.hops + 2):
            refused = bound(tool=_tool("logs_specialist"), args={}, tool_context=None)
            if refused is None:
                consulted.record(LOGS, {"findings": [_finding()] if gathers else []})
        return {"hypothesis": "the pods are out of memory", "confidence": "high"}

    return _run


def _asks_nobody(
    crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
) -> dict[str, Any]:
    """A manager that chose not to consult anyone, which is an ordinary result."""
    return {}


def _investigator(run: Any, breakers: CircuitBreakers | None = None) -> AdkInvestigator:
    return AdkInvestigator(
        crew=(LOGS, APM),
        run_diagnostician=run,
        run_report=lambda brief: {"headline": "checkout", "narrative": "The pods die."},
        breakers=breakers,
    )


def test_a_trip_with_findings_is_returned_marked_incomplete() -> None:
    """The findings in hand are no less true for the bound having been reached."""
    diagnosis = _investigator(
        _keeps_asking(gathers=True), CircuitBreakers(max_agent_hops=2)
    ).investigate(_target())

    assert diagnosis.findings.findings
    assert diagnosis.findings.retrieval_failures


def test_a_trip_with_findings_still_delivers_its_report() -> None:
    diagnosis = _investigator(
        _keeps_asking(gathers=True), CircuitBreakers(max_agent_hops=2)
    ).investigate(_target())

    assert diagnosis.headline
    assert diagnosis.hypothesis == "the pods are out of memory"


def test_the_report_says_which_bound_was_reached() -> None:
    """Not merely that it was incomplete: a reader has to tell the two apart."""
    diagnosis = _investigator(
        _keeps_asking(gathers=True), CircuitBreakers(max_agent_hops=2)
    ).investigate(_target())

    assert any(
        "consultations" in reason for reason in diagnosis.findings.retrieval_failures
    )
    assert any("2" in reason for reason in diagnosis.findings.retrieval_failures)


def test_a_trip_that_gathered_nothing_raises_rather_than_reporting() -> None:
    """While an attempt remains, learning nothing is not worth a message."""
    with pytest.raises(InvestigatorError, match="checkout"):
        _investigator(
            _keeps_asking(gathers=False), CircuitBreakers(max_agent_hops=2)
        ).investigate(_target())


def test_the_failure_names_the_bound_that_stopped_it() -> None:
    with pytest.raises(InvestigatorError, match="consultations"):
        _investigator(
            _keeps_asking(gathers=False), CircuitBreakers(max_agent_hops=2)
        ).investigate(_target())


def test_a_manager_that_chose_to_ask_nobody_is_still_an_ordinary_result() -> None:
    """Being stopped from asking and deciding not to ask are different facts."""
    diagnosis = _investigator(_asks_nobody).investigate(_target())

    assert diagnosis.findings.findings == ()
    assert diagnosis.findings.consulted == ()
    assert diagnosis.hypothesis is None


def test_an_investigation_within_every_bound_carries_no_incompleteness() -> None:
    def _asks_once(
        crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
        consulted.record(LOGS, {"findings": [_finding()]})
        return {"hypothesis": "the pods are out of memory", "confidence": "high"}

    diagnosis = _investigator(_asks_once).investigate(_target())

    assert diagnosis.findings.retrieval_failures == ()
    assert diagnosis.findings.findings
