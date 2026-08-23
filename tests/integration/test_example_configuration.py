"""The shipped examples, checked against the schema they claim to describe.

An example that has drifted is worse than none: an operator copies it, and
learns from a startup failure that a key was renamed. These read the real
files from the repository root rather than a fixture.
"""

from dataclasses import fields
from pathlib import Path

import pytest

from alert_triage.configuration.adapters.env_file import resolve_environment
from alert_triage.configuration.adapters.yaml import load_config
from alert_triage.configuration.settings import (
    CircuitBreakers,
    CriticalService,
    Grouping,
    Ingestion,
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
)
from alert_triage.triage.adapters.sqlite import LEDGER_PATH_VARIABLE

REPOSITORY_ROOT = Path(__file__).parents[2]
CONFIG_EXAMPLE = REPOSITORY_ROOT / "config.example.yaml"
ENV_EXAMPLE = REPOSITORY_ROOT / ".env.example"

SECTIONS = {
    "scope": Scope,
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
    """The environment variable each key of a section is overridable by."""
    return [f"{section}_{field.name}".upper() for field in fields(cls)]  # type: ignore[arg-type]


def test_the_example_config_is_a_config_the_loader_accepts() -> None:
    """Copied to config.yaml unedited, it has to start a run rather than fail one."""
    config = load_config(CONFIG_EXAMPLE, env={})

    assert config.scope.owner
    assert config.critical_services == {}


def test_the_example_config_states_the_defaults_it_documents() -> None:
    config = load_config(CONFIG_EXAMPLE, env={})

    assert config.grouping == Grouping()
    assert config.ingestion == Ingestion()
    assert config.re_notify == ReNotify()
    assert config.ledger == Ledger()
    assert config.circuit_breakers == CircuitBreakers()


@pytest.mark.parametrize(("section", "cls"), sorted(SECTIONS.items()))
def test_the_example_config_shows_every_key_of_every_section(
    section: str, cls: type[object]
) -> None:
    example = CONFIG_EXAMPLE.read_text()

    assert f"{section}:" in example
    for field in fields(cls):  # type: ignore[arg-type]
        assert f"{field.name}:" in example


def test_the_example_config_shows_every_threshold_of_a_critical_service() -> None:
    example = CONFIG_EXAMPLE.read_text()

    assert "critical_services:" in example
    for field in fields(CriticalService):
        assert f"{field.name}:" in example


@pytest.mark.parametrize("variable", CONNECTION_VARIABLES)
def test_the_example_env_file_names_every_connection_variable(variable: str) -> None:
    assert variable in ENV_EXAMPLE.read_text()


@pytest.mark.parametrize(("section", "cls"), sorted(SECTIONS.items()))
def test_the_example_env_file_names_every_behavior_override(
    section: str, cls: type[object]
) -> None:
    example = ENV_EXAMPLE.read_text()

    for name in _override_names(section, cls):
        assert name in example


def test_the_example_env_file_supplies_nothing_by_being_copied_unedited() -> None:
    """Every optional name stays commented out, so defaults remain the defaults."""
    environment = resolve_environment(ENV_EXAMPLE, {})

    assert set(environment) == {
        API_KEY_VARIABLE,
        APP_KEY_VARIABLE,
        MODEL_API_KEY_VARIABLE,
    }
    assert not any(environment.values())
