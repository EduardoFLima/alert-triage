import inspect
from dataclasses import fields

import pytest

from alert_triage.configuration.adapters.yaml.loader import ResolvedConfig
from alert_triage.notification.adapters.teams import (
    TEAMS_WEBHOOK_URL_VARIABLE,
    resolve_teams_webhook_url,
)

WEBHOOK_URL = "https://prod-1.westeurope.logic.azure.com/workflows/abc/triggers/manual"


def test_the_webhook_url_resolves_from_the_environment() -> None:
    assert (
        resolve_teams_webhook_url(env={TEAMS_WEBHOOK_URL_VARIABLE: WEBHOOK_URL})
        == WEBHOOK_URL
    )


def test_saying_nothing_about_the_channel_leaves_it_inactive() -> None:
    assert resolve_teams_webhook_url(env={}) is None


def test_an_empty_variable_leaves_the_channel_inactive_rather_than_half_open() -> None:
    assert resolve_teams_webhook_url(env={TEAMS_WEBHOOK_URL_VARIABLE: ""}) is None


def test_the_environment_is_read_from_the_process_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TEAMS_WEBHOOK_URL_VARIABLE, WEBHOOK_URL)

    assert resolve_teams_webhook_url() == WEBHOOK_URL


def test_the_webhook_url_has_no_config_file_to_be_read_from() -> None:
    """The resolver takes an environment and nothing else: there is no file path."""
    assert list(inspect.signature(resolve_teams_webhook_url).parameters) == ["env"]


def test_a_webhook_url_written_into_the_config_file_has_nowhere_to_land() -> None:
    """No resolved config section names a webhook, so a shared file cannot carry one."""
    sections = {field.name for field in fields(ResolvedConfig)}

    assert not sections & {"teams", "webhook", "notification", "notifications"}
