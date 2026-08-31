"""A report is worth more than its prose, and the prose is the last thing added.

Everything a report carries was gathered before any of it was worded, so losing
it to the wording would be the worst trade this investigation could make. The
fallback is not emergency code: it is the same renderer with nothing written
above it.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.consultation import (
    MAX_CONSULTATIONS,
    Consulted,
    bound_consultations_callback,
)
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
    toolsets=(Toolset(name="core", tools=("search_datadog_logs",)),),
)


def _target() -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON + timedelta(minutes=20)),
        alert_count=1,
    )


def _finds(consults: tuple[str, ...] = ("logs_specialist",)) -> Any:
    def _run(
        crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
        for name in consults:
            specialist = consulted.named(name)
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


def _investigator(run_report: Any) -> AdkInvestigator:
    return AdkInvestigator(
        crew=(LOGS,), run_diagnostician=_finds(), run_report=run_report
    )


def _briefs(collected: list[str]) -> Any:
    def _run(brief: str) -> dict[str, Any]:
        collected.append(brief)
        return {"headline": "checkout is out of memory", "narrative": "The pods die."}

    return _run


def test_the_wording_runs_over_the_hypothesis_and_the_surviving_findings() -> None:
    briefs: list[str] = []

    _investigator(_briefs(briefs)).investigate(_target())

    assert "the pods are out of memory" in briefs[0]
    assert "high" in briefs[0]
    assert "OOMKilled recurs" in briefs[0]


def test_the_account_is_what_was_written_over_the_evidence_it_rests_on() -> None:
    diagnosis = _investigator(_briefs([])).investigate(_target())

    assert diagnosis.headline == "checkout is out of memory"
    assert "The pods die." in diagnosis.account
    assert "OOMKilled" in diagnosis.account


def test_a_wording_failure_still_delivers_the_report() -> None:
    def _explodes(brief: str) -> dict[str, Any]:
        raise RuntimeError("the model refused")

    diagnosis = _investigator(_explodes).investigate(_target())

    assert diagnosis.hypothesis == "the pods are out of memory"
    assert "OOMKilled recurs" in diagnosis.account
    assert diagnosis.headline


def test_an_unusable_answer_falls_back_the_same_way() -> None:
    def _rambles(brief: str) -> dict[str, Any]:
        return {"headline": "", "narrative": "   "}

    diagnosis = _investigator(_rambles).investigate(_target())

    assert "OOMKilled recurs" in diagnosis.account
    assert "checkout" in diagnosis.headline


def test_a_composed_account_still_states_the_conclusion() -> None:
    def _explodes(brief: str) -> dict[str, Any]:
        raise RuntimeError("the model refused")

    diagnosis = _investigator(_explodes).investigate(_target())

    assert "the pods are out of memory" in diagnosis.account
    assert "high" in diagnosis.account


def test_a_headline_spanning_lines_is_flattened_rather_than_refused() -> None:
    """A channel needs one line; losing the report over a stray newline is worse."""

    def _wraps(brief: str) -> dict[str, Any]:
        return {"headline": "checkout is\nout of memory", "narrative": "The pods die."}

    diagnosis = _investigator(_wraps).investigate(_target())

    assert diagnosis.headline == "checkout is out of memory"


def test_an_investigation_that_spent_its_questions_still_concludes() -> None:
    """The findings already in hand are no less true for the budget running out."""

    def _keeps_asking(
        crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
        bound = bound_consultations_callback(consulted)
        for _ in range(MAX_CONSULTATIONS + 2):
            refused = bound(
                tool=type("_T", (), {"name": "logs_specialist"})(),
                args={},
                tool_context=None,
            )
            if refused is None:
                consulted.record(
                    LOGS,
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

    diagnosis = AdkInvestigator(
        crew=(LOGS,), run_diagnostician=_keeps_asking, run_report=_briefs([])
    ).investigate(_target())

    assert diagnosis.hypothesis == "the pods are out of memory"
    assert len(diagnosis.findings.findings) == MAX_CONSULTATIONS


def test_an_investigation_cut_short_is_reported_as_cut_short() -> None:
    """Not as one that chose to stop: it wanted to ask more and could not."""

    def _keeps_asking(
        crew: Any, consulted: Consulted, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
        bound = bound_consultations_callback(consulted)
        for _ in range(MAX_CONSULTATIONS + 1):
            if (
                bound(
                    tool=type("_T", (), {"name": "logs_specialist"})(),
                    args={},
                    tool_context=None,
                )
                is None
            ):
                consulted.record(LOGS, {"findings": []})
        return {"hypothesis": "", "confidence": "low"}

    diagnosis = AdkInvestigator(
        crew=(LOGS,), run_diagnostician=_keeps_asking, run_report=_briefs([])
    ).investigate(_target())

    assert not diagnosis.findings.complete
    assert any("spent its" in why for why in diagnosis.findings.retrieval_failures)
