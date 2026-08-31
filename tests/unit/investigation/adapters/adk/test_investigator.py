"""What an investigation offers its manager, what it asks, and what it concludes.

The crew is no longer walked. A manager is offered every specialist and consults
the ones this incident needs, so the two facts worth asserting are what it was
given to choose from and what it actually chose — neither of which a fixed
sequence had to make observable.

Everything here runs with no model and no network: the manager is a stub that
consults whichever specialists the test names.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.consultation import Consulted
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.adk.investigator import AdkInvestigator
from alert_triage.investigation.contract import (
    Confidence,
    InvestigationTarget,
    Signal,
)
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
        toolsets=(Toolset(name="core", tools=("search_datadog_logs",)),),
    )


LOGS = _specialist("logs_specialist", Signal.LOGS)
APM = _specialist("apm_specialist", Signal.APM)
TRACE = _specialist("trace_specialist", Signal.TRACE)


def _target() -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON + timedelta(minutes=20)),
        alert_count=1,
    )


def _cites(cites: list[str], observation: str = "errors recur") -> dict[str, Any]:
    return {"observation": observation, "occurrences": 3, "cites": cites}


def _manager(
    *,
    consults: tuple[str, ...] = ("logs_specialist",),
    retrieves: tuple[str, ...] = ("OOMKilled",),
    fails: int = 0,
    reports: dict[str, list[dict[str, Any]]] | None = None,
    hypothesis: str = "the pods are out of memory",
    confidence: str = "high",
    offered_to: list[tuple[str, ...]] | None = None,
) -> Any:
    """A stand-in manager: it consults what the test names, then concludes."""

    def _run(
        crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        if offered_to is not None:
            offered_to.append(tuple(one.name for one in crew))
        for _ in range(fails):
            retrieved.refuse_evidence("the platform could not be reached")
        if retrieves:
            retrieved.retain_evidence(
                {"logs": [{"message": message} for message in retrieves]}
            )
        for name in consults:
            specialist = consulted.named(name)
            assert specialist is not None
            found = (reports or {}).get(name, [])
            consulted.record(specialist, {"findings": found})
        return {"hypothesis": hypothesis, "confidence": confidence}

    return _run


def _words(headline: str = "checkout is out of memory") -> Any:
    def _run(brief: str) -> dict[str, Any]:
        return {"headline": headline, "narrative": f"About: {brief[:20]}"}

    return _run


def _investigator(**manager: Any) -> AdkInvestigator:
    return AdkInvestigator(
        crew=(LOGS, APM, TRACE),
        run_diagnostician=_manager(**manager),
        run_report=_words(),
    )


def test_every_specialist_is_offered_to_the_manager() -> None:
    offered: list[tuple[str, ...]] = []

    _investigator(offered_to=offered).investigate(_target())

    assert offered == [("logs_specialist", "apm_specialist", "trace_specialist")]


def test_only_the_specialists_the_manager_asked_for_are_consulted() -> None:
    diagnosis = _investigator(
        consults=("apm_specialist", "logs_specialist"),
        reports={"apm_specialist": [_cites(["call-1/item-1"], "latency doubled")]},
    ).investigate(_target())

    assert diagnosis.findings.consulted == (Signal.APM, Signal.LOGS)


def test_a_specialist_that_was_never_consulted_names_no_signal() -> None:
    """The failure this whole slice exists to prevent, asserted directly."""
    diagnosis = _investigator(consults=("logs_specialist",)).investigate(_target())

    assert diagnosis.findings.consulted == (Signal.LOGS,)
    assert Signal.TRACE not in diagnosis.findings.consulted
    assert Signal.APM not in diagnosis.findings.consulted


def test_findings_come_back_naming_the_signal_of_the_specialist_that_found_them() -> (
    None
):
    diagnosis = _investigator(
        consults=("logs_specialist", "apm_specialist"),
        reports={
            "logs_specialist": [_cites(["call-1/item-1"], "errors recur")],
            "apm_specialist": [_cites(["call-1"], "latency doubled")],
        },
    ).investigate(_target())

    assert [(one.signal, one.observation) for one in diagnosis.findings.findings] == [
        (Signal.LOGS, "errors recur"),
        (Signal.APM, "latency doubled"),
    ]


def test_the_investigation_carries_the_hypothesis_and_its_confidence() -> None:
    diagnosis = _investigator(
        reports={"logs_specialist": [_cites(["call-1/item-1"])]},
        hypothesis="the pods are out of memory",
        confidence="medium",
    ).investigate(_target())

    assert diagnosis.hypothesis == "the pods are out of memory"
    assert diagnosis.confidence is Confidence.MEDIUM


def test_a_confidence_level_nobody_declared_is_reported_as_none() -> None:
    diagnosis = _investigator(
        reports={"logs_specialist": [_cites(["call-1/item-1"])]},
        confidence="fairly sure",
    ).investigate(_target())

    assert diagnosis.hypothesis is not None
    assert diagnosis.confidence is None


def test_a_hypothesis_with_no_surviving_finding_beneath_it_is_dropped() -> None:
    diagnosis = _investigator(
        reports={"logs_specialist": [_cites(["call-9/item-1"], "invented")]}
    ).investigate(_target())

    assert diagnosis.findings.findings == ()
    assert diagnosis.hypothesis is None
    assert diagnosis.confidence is None


def test_an_investigation_that_consulted_nobody_completes_without_concluding() -> None:
    """A manager that asked nothing is not a platform that could not be reached."""
    diagnosis = _investigator(consults=(), retrieves=()).investigate(_target())

    assert diagnosis.findings.findings == ()
    assert diagnosis.findings.consulted == ()
    assert diagnosis.hypothesis is None


def test_every_retrieval_failing_is_still_a_failed_investigation() -> None:
    with pytest.raises(InvestigatorError, match="could not be reached"):
        _investigator(retrieves=(), fails=2).investigate(_target())


def test_some_retrievals_failing_still_returns_findings_marked_incomplete() -> None:
    diagnosis = _investigator(
        fails=1, reports={"logs_specialist": [_cites(["call-1/item-1"])]}
    ).investigate(_target())

    assert len(diagnosis.findings.findings) == 1
    assert not diagnosis.findings.complete


def test_a_manager_that_errors_outright_fails_the_investigation() -> None:
    def _explodes(crew: Any, consulted: Any, retrieved: Any, prompt: str) -> Any:
        raise RuntimeError("the model refused")

    investigator = AdkInvestigator(
        crew=(LOGS,), run_diagnostician=_explodes, run_report=_words()
    )

    with pytest.raises(InvestigatorError, match="checkout"):
        investigator.investigate(_target())


def test_the_manager_is_told_about_the_target_it_is_investigating() -> None:
    prompts: list[str] = []

    def _capture(crew: Any, consulted: Any, retrieved: Any, prompt: str) -> Any:
        prompts.append(prompt)
        return {"hypothesis": "", "confidence": "low"}

    AdkInvestigator(
        crew=(LOGS,), run_diagnostician=_capture, run_report=_words()
    ).investigate(_target())

    assert "checkout" in prompts[0]
    assert NOON.isoformat() in prompts[0]


def test_each_investigation_starts_with_nothing_citable() -> None:
    """An identifier from an earlier incident must not resolve in a later one."""
    diagnosis = _investigator(
        retrieves=(), reports={"logs_specialist": [_cites(["call-1/item-1"])]}
    ).investigate(_target())

    assert diagnosis.findings.findings == ()


def test_a_manager_that_never_concluded_still_reports_what_it_found(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Findings are real whether or not the reasoning got as far as a conclusion."""

    def _stops_early(
        crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
        specialist = consulted.named("apm_specialist")
        assert specialist is not None
        consulted.record(specialist, {"findings": [_cites(["call-1/item-1"])]})
        return {}

    investigator = AdkInvestigator(
        crew=(LOGS, APM), run_diagnostician=_stops_early, run_report=_words()
    )

    with caplog.at_level(logging.WARNING):
        diagnosis = investigator.investigate(_target())

    assert len(diagnosis.findings.findings) == 1
    assert diagnosis.hypothesis is None
    assert "concluded nothing" in caplog.text or "no conclusion" in caplog.text


def test_reaching_no_conclusion_is_distinguishable_from_answering_with_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One never answered in its schema; the other answered and had nothing."""

    def _answers_emptily(
        crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
        specialist = consulted.named("apm_specialist")
        assert specialist is not None
        consulted.record(specialist, {"findings": [_cites(["call-1/item-1"])]})
        return {"hypothesis": "", "confidence": "low"}

    investigator = AdkInvestigator(
        crew=(LOGS, APM), run_diagnostician=_answers_emptily, run_report=_words()
    )

    with caplog.at_level(logging.WARNING):
        investigator.investigate(_target())

    assert "no conclusion" not in caplog.text
