from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.adk.investigator import AdkInvestigator
from alert_triage.investigation.contract import InvestigationTarget, Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset
from alert_triage.investigation.ports.investigator import InvestigatorError
from alert_triage.shared.window import Window

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


class _Reported(BaseModel):
    findings: list[str] = []


def _target() -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON),
        alert_count=1,
    )


def _specialist(name: str = "logs_specialist") -> Specialist:
    return Specialist(
        name=name,
        signal=Signal.LOGS,
        instruction="Look at the logs.",
        output_schema=_Reported,
        toolsets=(Toolset(name="core", tools=("search_datadog_logs",)),),
    )


def _logs(*messages: str) -> dict[str, Any]:
    return {"logs": [{"message": message} for message in messages]}


def _reports(
    *,
    retrieves: tuple[str, ...] = ("OOMKilled",),
    fails: int = 0,
    findings: list[dict[str, Any]] | None = None,
) -> Any:
    """A stand-in for a specialist: it retrieves what we say, then reports."""

    def _run(specialist: Specialist, retrieved: Retrieved, prompt: str) -> Any:
        for _ in range(fails):
            retrieved.refuse(f"{specialist.name} could not reach the platform")
        if retrieves:
            retrieved.retain(_logs(*retrieves))
        return {"findings": findings if findings is not None else []}

    return _run


def _cites(cites: list[str], observation: str = "errors recur") -> dict[str, Any]:
    return {"observation": observation, "occurrences": 3, "cites": cites}


def test_the_findings_are_built_from_what_the_platform_returned() -> None:
    investigator = AdkInvestigator(
        crew=(_specialist(),),
        run_specialist=_reports(findings=[_cites(["call-1/item-1"])]),
    )

    (finding,) = investigator.investigate(_target()).findings

    assert finding.signal is Signal.LOGS
    assert finding.examples[0].summary == "OOMKilled"


def test_every_specialist_in_the_crew_contributes_to_one_result() -> None:
    crew = (_specialist("logs_specialist"), _specialist("apm_specialist"))
    investigator = AdkInvestigator(
        crew=crew, run_specialist=_reports(findings=[_cites(["call-1/item-1"])])
    )

    findings = investigator.investigate(_target())

    assert len(findings.findings) == 2
    assert findings.complete


def test_a_caller_cannot_tell_how_many_specialists_ran() -> None:
    """The result has the same shape whoever contributed to it."""
    one = AdkInvestigator(crew=(_specialist(),), run_specialist=_reports())
    two = AdkInvestigator(
        crew=(_specialist("logs_specialist"), _specialist("apm_specialist")),
        run_specialist=_reports(),
    )

    assert type(one.investigate(_target())) is type(two.investigate(_target()))


def test_each_finding_names_the_signal_its_specialist_reports_under() -> None:
    investigator = AdkInvestigator(
        crew=(_specialist(),),
        run_specialist=_reports(findings=[_cites(["call-1/item-1"])]),
    )

    (finding,) = investigator.investigate(_target()).findings

    assert finding.signal is Signal.LOGS


def test_an_investigation_that_found_nothing_returns_empty_findings() -> None:
    investigator = AdkInvestigator(crew=(_specialist(),), run_specialist=_reports())

    findings = investigator.investigate(_target())

    assert findings.findings == ()
    assert not findings.anything_notable
    assert findings.complete


def test_findings_are_returned_marked_incomplete_when_a_retrieval_failed() -> None:
    investigator = AdkInvestigator(
        crew=(_specialist(),),
        run_specialist=_reports(fails=1, findings=[_cites(["call-1/item-1"])]),
    )

    findings = investigator.investigate(_target())

    assert len(findings.findings) == 1
    assert not findings.complete
    assert "could not reach the platform" in findings.retrieval_failures[0]


def test_an_investigation_whose_every_retrieval_failed_is_a_failure() -> None:
    """However confidently the model reports having found nothing."""
    investigator = AdkInvestigator(
        crew=(_specialist(),),
        run_specialist=_reports(
            retrieves=(), fails=2, findings=[_cites(["call-1/item-1"])]
        ),
    )

    with pytest.raises(InvestigatorError, match="could not reach the platform"):
        investigator.investigate(_target())


def test_an_investigation_that_never_looked_is_not_a_failure() -> None:
    """A model that chose not to search looked and saw nothing to say."""
    investigator = AdkInvestigator(
        crew=(_specialist(),), run_specialist=_reports(retrieves=())
    )

    findings = investigator.investigate(_target())

    assert findings.findings == ()
    assert findings.complete


def test_a_specialist_that_errors_outright_fails_the_investigation() -> None:
    def _explodes(specialist: Specialist, retrieved: Retrieved, prompt: str) -> Any:
        raise RuntimeError("the model refused")

    investigator = AdkInvestigator(crew=(_specialist(),), run_specialist=_explodes)

    with pytest.raises(InvestigatorError, match="refused"):
        investigator.investigate(_target())


def test_a_failed_investigation_names_the_service_it_concerned() -> None:
    """The target is all a failure has left to say what it was about."""

    def _explodes(specialist: Specialist, retrieved: Retrieved, prompt: str) -> Any:
        raise RuntimeError("the model refused")

    investigator = AdkInvestigator(crew=(_specialist(),), run_specialist=_explodes)

    with pytest.raises(InvestigatorError, match="checkout"):
        investigator.investigate(_target())


def test_a_specialist_is_told_about_the_target_it_is_investigating() -> None:
    prompts: list[str] = []

    def _capture(specialist: Specialist, retrieved: Retrieved, prompt: str) -> Any:
        prompts.append(prompt)
        return {"findings": []}

    AdkInvestigator(crew=(_specialist(),), run_specialist=_capture).investigate(
        _target()
    )

    assert "checkout" in prompts[0]
    assert NOON.isoformat() in prompts[0]


def test_a_fabricated_citation_does_not_reach_the_findings() -> None:
    investigator = AdkInvestigator(
        crew=(_specialist(),),
        run_specialist=_reports(findings=[_cites(["call-9/item-1"], "invented")]),
    )

    assert investigator.investigate(_target()).findings == ()


def test_each_investigation_starts_with_nothing_citable() -> None:
    """An identifier from an earlier incident must not resolve in a later one."""
    investigator = AdkInvestigator(
        crew=(_specialist(),),
        run_specialist=_reports(retrieves=(), findings=[_cites(["call-1/item-1"])]),
    )

    assert investigator.investigate(_target()).findings == ()


def test_what_one_specialist_retrieved_is_citable_by_the_next() -> None:
    """One investigation, one body of evidence: the crew shares what it gathered."""

    def _run(specialist: Specialist, retrieved: Retrieved, prompt: str) -> Any:
        if specialist.name == "logs_specialist":
            retrieved.retain(_logs("OOMKilled"))
            return {"findings": []}
        return {"findings": [_cites(["call-1/item-1"], "the logs show it too")]}

    investigator = AdkInvestigator(
        crew=(_specialist("logs_specialist"), _specialist("apm_specialist")),
        run_specialist=_run,
    )

    (finding,) = investigator.investigate(_target()).findings

    assert finding.observation == "the logs show it too"


class _Links:
    """A platform's addresses, standing in for the one bound to a real site."""

    def to_retrieval(self, args: Any) -> str | None:
        return "https://platform/search"

    def to_item(self, payload: Any, within: str | None) -> str | None:
        return within


def test_the_evidence_of_each_investigation_is_addressed_by_the_platforms_linker() -> (
    None
):
    """One linker per deployment, reaching the ``Retrieved`` of every investigation."""
    investigator = AdkInvestigator(
        crew=(_specialist(),),
        run_specialist=_reports(
            findings=[
                {
                    "observation": "OOMKilled recurs",
                    "occurrences": 3,
                    "cites": ["call-1/item-1"],
                }
            ]
        ),
        links=_Links(),
    )

    (finding,) = investigator.investigate(_target()).findings

    assert finding.examples[0].url == "https://platform/search"


def test_an_investigator_with_no_linker_still_investigates() -> None:
    """Evidence without an address is still evidence, and a test says so."""
    investigator = AdkInvestigator(
        crew=(_specialist(),),
        run_specialist=_reports(
            findings=[
                {
                    "observation": "OOMKilled recurs",
                    "occurrences": 3,
                    "cites": ["call-1/item-1"],
                }
            ]
        ),
    )

    (finding,) = investigator.investigate(_target()).findings

    assert finding.examples[0].url is None
