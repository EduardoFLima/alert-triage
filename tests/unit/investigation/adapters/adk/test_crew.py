from datetime import UTC, datetime
from typing import Any

import pytest

from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import SpecialistModel
from alert_triage.investigation.adapters.adk.crew import CREW, crew_for
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.adk.investigator import AdkInvestigator
from alert_triage.investigation.adapters.datadog.specialists.apm import APM_SPECIALIST
from alert_triage.investigation.adapters.datadog.specialists.infrastructure import (
    INFRASTRUCTURE_SPECIALIST,
)
from alert_triage.investigation.adapters.datadog.specialists.logs import LOGS_SPECIALIST
from alert_triage.investigation.adapters.datadog.specialists.trace import (
    TRACE_SPECIALIST,
)
from alert_triage.investigation.contract import InvestigationTarget, Signal
from alert_triage.investigation.domain.specialist import Specialist
from alert_triage.shared.window import Window


def test_a_crew_nobody_configured_reasons_on_the_deployments_model() -> None:
    assert crew_for({}) == CREW
    assert all(specialist.model is None for specialist in crew_for({}))


def test_a_configured_specialist_reasons_on_the_model_it_was_given() -> None:
    crew = crew_for({"logs_specialist": SpecialistModel(model="a-bigger-model")})

    (logs,) = [one for one in crew if one.name == "logs_specialist"]
    assert logs.model == "a-bigger-model"


def test_configuring_one_specialist_leaves_its_declaration_alone() -> None:
    """The declaration is the source; configuration produces a crew from it."""
    crew_for({"logs_specialist": SpecialistModel(model="a-bigger-model")})

    assert LOGS_SPECIALIST.model is None


def test_configuring_a_specialist_nobody_declared_is_refused_by_name() -> None:
    with pytest.raises(ConfigError, match="metrics_specialist"):
        crew_for({"metrics_specialist": SpecialistModel(model="a-model")})


def test_the_refusal_says_which_specialists_there_are() -> None:
    with pytest.raises(ConfigError, match="logs_specialist"):
        crew_for({"metrics_specialist": SpecialistModel(model="a-model")})


def test_the_crew_is_every_specialist_that_has_been_declared() -> None:
    assert set(CREW) == {
        LOGS_SPECIALIST,
        APM_SPECIALIST,
        TRACE_SPECIALIST,
        INFRASTRUCTURE_SPECIALIST,
    }


def test_the_crew_names_each_specialist_once() -> None:
    names = [specialist.name for specialist in CREW]

    assert len(names) == len(set(names))


def test_the_crew_covers_every_signal_a_finding_can_be_drawn_from() -> None:
    """A signal nothing reports under is a signal no report may claim."""
    assert {specialist.signal for specialist in CREW} == set(Signal)


@pytest.mark.parametrize("name", [specialist.name for specialist in CREW])
def test_any_specialist_can_be_given_a_model_of_its_own_by_name(name: str) -> None:
    crew = crew_for({name: SpecialistModel(model="a-bigger-model")})

    (configured,) = [one for one in crew if one.name == name]
    assert configured.model == "a-bigger-model"
    assert all(one.model is None for one in crew if one.name != name)


def _target() -> InvestigationTarget:
    noon = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    return InvestigationTarget(
        service="checkout", window=Window(start=noon, end=noon), alert_count=1
    )


def _each_reports_what_it_retrieved(
    specialist: Specialist, retrieved: Retrieved, prompt: str
) -> dict[str, Any]:
    """A stand-in for every specialist: it retrieves, then reports what it saw."""
    offered = retrieved.retain_evidence(
        {"logs": [{"message": f"{specialist.name} saw this"}]}
    )
    return {
        "findings": [
            {
                "observation": f"{specialist.name} observed something",
                "occurrences": 1,
                "cites": [offered["items"][0]["id"]],
            }
        ]
    }


def test_an_investigation_over_the_whole_crew_reports_from_every_specialist() -> None:
    investigator = AdkInvestigator(
        crew=CREW, run_specialist=_each_reports_what_it_retrieved
    )

    findings = investigator.investigate(_target())

    assert [finding.signal for finding in findings.findings] == [
        specialist.signal for specialist in CREW
    ]
    assert len({finding.signal for finding in findings.findings}) > 1
    assert findings.complete


def test_a_crew_of_four_produces_what_a_crew_of_one_does_and_no_new_shape() -> None:
    """The claim slice 7 made: a specialist costs a declaration and nothing else."""
    alone = AdkInvestigator(
        crew=(LOGS_SPECIALIST,), run_specialist=_each_reports_what_it_retrieved
    ).investigate(_target())
    whole = AdkInvestigator(
        crew=CREW, run_specialist=_each_reports_what_it_retrieved
    ).investigate(_target())

    assert type(whole) is type(alone)
    assert {type(finding) for finding in whole.findings} == {
        type(finding) for finding in alone.findings
    }
    assert len(whole.findings) == len(CREW)


def test_each_finding_carries_the_evidence_its_own_specialist_retrieved() -> None:
    """Findings arrive grouped because the crew is walked in order."""
    investigator = AdkInvestigator(
        crew=CREW, run_specialist=_each_reports_what_it_retrieved
    )

    findings = investigator.investigate(_target())

    for specialist, finding in zip(CREW, findings.findings, strict=True):
        assert finding.examples[0].summary == f"{specialist.name} saw this"
