"""Urgency is something an investigation is told, not something it looks up.

A deployment declares a service critical in its configuration, and the whole of
what reaches here is one field on the target. That is what keeps a specialist
free of settings: it reasons about the incident it was handed, and the same
description that tells the agents what to consult tells the writer what to say.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.consultation import Consulted
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.adk.investigator import AdkInvestigator
from alert_triage.investigation.contract import InvestigationTarget, Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset
from alert_triage.shared.window import Window

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


class _Reported(BaseModel):
    findings: list[dict[str, Any]] = []


LOGS = Specialist(
    name="logs_specialist",
    signal=Signal.LOGS,
    instruction="Look.",
    output_schema=_Reported,
    toolsets=(
        Toolset(provider="datadog", name="core", tools=("search_datadog_logs",)),
    ),
)


def _target(*, critical: bool) -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON + timedelta(minutes=20)),
        alert_count=1,
        critical=critical,
    )


def _finds(asked: list[str], crews: list[tuple[Specialist, ...]]) -> Any:
    """A diagnostician that finds one thing, recording what it was asked over."""

    def _run(
        crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        asked.append(prompt)
        crews.append(tuple(crew))
        retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
        specialist = consulted.named("logs_specialist")
        assert specialist is not None
        consulted.record(
            specialist,
            {
                "findings": [
                    {
                        "observation": "OOMKilled recurs",
                        "occurrences": 3,
                        "cites": ["call-1/item-1"],
                    }
                ]
            },
        )
        return {"hypothesis": "the pods are out of memory", "confidence": "high"}

    return _run


def _writes(briefs: list[str]) -> Any:
    def _run(brief: str) -> dict[str, Any]:
        briefs.append(brief)
        return {"headline": "checkout is out of memory", "narrative": "The pods die."}

    return _run


def test_a_critical_services_incident_is_stated_as_critical_to_the_agents() -> None:
    asked: list[str] = []

    AdkInvestigator(
        crew=(LOGS,),
        run_diagnostician=_finds(asked, []),
        run_report=_writes([]),
    ).investigate(_target(critical=True))

    assert "critical" in asked[0].lower()


def test_the_writer_is_told_the_service_is_critical() -> None:
    """The brief is built on the same description, so one field reaches both."""
    briefs: list[str] = []

    AdkInvestigator(
        crew=(LOGS,),
        run_diagnostician=_finds([], []),
        run_report=_writes(briefs),
    ).investigate(_target(critical=True))

    assert "critical" in briefs[0].lower()


def test_an_investigation_is_told_urgency_rather_than_looking_it_up() -> None:
    """Nothing but the target differs, and nothing but the target decides."""
    asked: list[str] = []
    briefs: list[str] = []
    investigator = AdkInvestigator(
        crew=(LOGS,),
        run_diagnostician=_finds(asked, []),
        run_report=_writes(briefs),
    )

    investigator.investigate(_target(critical=True))
    investigator.investigate(_target(critical=False))

    assert "critical" in asked[0].lower()
    assert "not declared critical" in asked[1].lower()
    assert "not declared critical" in briefs[1].lower()


def test_criticality_changes_no_specialist_and_no_bound() -> None:
    """It alters how the incident is characterised, never what may be gathered."""
    crews: list[tuple[Specialist, ...]] = []
    investigator = AdkInvestigator(
        crew=(LOGS,),
        run_diagnostician=_finds([], crews),
        run_report=_writes([]),
    )

    critical = investigator.investigate(_target(critical=True))
    ordinary = investigator.investigate(_target(critical=False))

    assert crews[0] == crews[1]
    assert critical.findings.consulted == ordinary.findings.consulted
