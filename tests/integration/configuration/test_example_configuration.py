from dataclasses import fields
from pathlib import Path

import pytest

from alert_triage.app.verbosity import LOG_LEVEL, LOG_TOOL_CALLBACK
from alert_triage.configuration.adapters.env_file import resolve_environment
from alert_triage.configuration.adapters.yaml import load_config
from alert_triage.configuration.settings import (
    CircuitBreakers,
    Grouping,
    Ingestion,
    Investigation,
    Ledger,
    ReNotify,
    Scope,
)
from alert_triage.investigation.adapters.adk.credentials import (
    API_KEY_VARIABLE as MODEL_API_KEY_VARIABLE,
)
from alert_triage.investigation.adapters.adk.credentials import (
    ENTERPRISE_VARIABLE,
    LOCATION_VARIABLE,
    PROJECT_VARIABLE,
)
from alert_triage.investigation.adapters.crew.roster import CREW
from alert_triage.notification.adapters.email.settings import (
    EMAIL_FROM_VARIABLE,
    EMAIL_TO_VARIABLE,
    SMTP_HOST_VARIABLE,
    SMTP_PASSWORD_VARIABLE,
    SMTP_PORT_VARIABLE,
    SMTP_USERNAME_VARIABLE,
)
from alert_triage.notification.adapters.teams.settings import TEAMS_WEBHOOK_URL_VARIABLE
from alert_triage.triage.adapters.datadog.connection import (
    API_KEY_VARIABLE,
    APP_KEY_VARIABLE,
    SITE_VARIABLE,
    WEB_SUBDOMAIN_VARIABLE,
)
from alert_triage.triage.adapters.sqlite import LEDGER_PATH_VARIABLE

SECTIONS = {
    "scope": Scope,
    "investigation": Investigation,
    "grouping": Grouping,
    "ingestion": Ingestion,
    "re_notify": ReNotify,
    "ledger": Ledger,
    "circuit_breakers": CircuitBreakers,
}

CONNECTION_VARIABLES = (
    API_KEY_VARIABLE,
    APP_KEY_VARIABLE,
    SITE_VARIABLE,
    WEB_SUBDOMAIN_VARIABLE,
    MODEL_API_KEY_VARIABLE,
    ENTERPRISE_VARIABLE,
    PROJECT_VARIABLE,
    LOCATION_VARIABLE,
    LEDGER_PATH_VARIABLE,
    SMTP_HOST_VARIABLE,
    SMTP_PORT_VARIABLE,
    SMTP_USERNAME_VARIABLE,
    SMTP_PASSWORD_VARIABLE,
    EMAIL_FROM_VARIABLE,
    EMAIL_TO_VARIABLE,
    TEAMS_WEBHOOK_URL_VARIABLE,
)


def _override_names(section: str, cls: type[object]) -> list[str]:
    return [f"{section}_{field.name}".upper() for field in fields(cls)]  # type: ignore[arg-type]


def test_the_example_config_is_a_config_the_loader_accepts(
    config_example: Path,
) -> None:
    config = load_config(config_example, env={})

    assert config.scope.owner


def test_the_example_config_states_the_defaults_it_documents(
    config_example: Path,
) -> None:
    config = load_config(config_example, env={})

    assert config.scope.env == Scope.DEFAULT_ENV
    assert config.grouping == Grouping()
    assert config.investigation == Investigation()
    assert config.ingestion == Ingestion()
    assert config.re_notify == ReNotify()
    assert config.ledger == Ledger()
    assert config.circuit_breakers == CircuitBreakers()


@pytest.mark.parametrize(("section", "cls"), sorted(SECTIONS.items()))
def test_the_example_config_shows_every_key_of_every_section(
    section: str, cls: type[object], config_example: Path
) -> None:
    example = config_example.read_text()

    assert f"{section}:" in example
    for field in fields(cls):  # type: ignore[arg-type]
        assert f"{field.name}:" in example


@pytest.mark.parametrize("variable", CONNECTION_VARIABLES)
def test_the_example_env_file_names_every_connection_variable(
    variable: str, env_example: Path
) -> None:
    assert variable in env_example.read_text()


@pytest.mark.parametrize(("section", "cls"), sorted(SECTIONS.items()))
def test_the_example_env_file_names_every_behavior_override(
    section: str, cls: type[object], env_example: Path
) -> None:
    example = env_example.read_text()

    for name in _override_names(section, cls):
        assert name in example


@pytest.mark.parametrize("variable", (LOG_LEVEL, LOG_TOOL_CALLBACK))
def test_the_example_env_file_names_how_much_a_run_says(
    variable: str, env_example: Path
) -> None:
    assert variable in env_example.read_text()


def test_the_example_env_file_supplies_nothing_by_being_copied_unedited(
    env_example: Path,
) -> None:
    environment = resolve_environment(env_example, {})

    assert set(environment) == {
        API_KEY_VARIABLE,
        APP_KEY_VARIABLE,
        MODEL_API_KEY_VARIABLE,
    }
    assert not any(environment.values())


@pytest.mark.parametrize("specialist", [one.name for one in CREW])
def test_the_example_config_names_every_specialist_that_may_be_given_a_model(
    specialist: str, config_example: Path
) -> None:
    assert specialist in config_example.read_text()
