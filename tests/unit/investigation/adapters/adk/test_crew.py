import pytest

from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import SpecialistModel
from alert_triage.investigation.adapters.adk.crew import CREW, crew_for
from alert_triage.investigation.adapters.datadog.specialists.logs import LOGS_SPECIALIST


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
