import pytest

from alert_triage.adapters.datadog.connection import (
    DEFAULT_SITE,
    DatadogConnection,
    resolve_connection,
)
from alert_triage.ports.config import ConfigError

CREDENTIALS = {"DD_API_KEY": "api-key", "DD_APP_KEY": "app-key"}


def test_site_falls_back_to_the_documented_default() -> None:
    connection = resolve_connection(env=CREDENTIALS)

    assert connection.site == DEFAULT_SITE == "datadoghq.com"


def test_site_is_taken_from_the_environment_for_another_region() -> None:
    connection = resolve_connection(env=CREDENTIALS | {"DD_SITE": "datadoghq.eu"})

    assert connection.site == "datadoghq.eu"


def test_credentials_resolve_from_the_environment() -> None:
    connection = resolve_connection(env=CREDENTIALS)

    assert connection == DatadogConnection(
        site="datadoghq.com", api_key="api-key", app_key="app-key"
    )


def test_missing_credentials_are_reported_as_required() -> None:
    with pytest.raises(ConfigError, match="DD_API_KEY"):
        resolve_connection(env={})


def test_a_partially_supplied_credential_pair_is_reported() -> None:
    with pytest.raises(ConfigError, match="DD_APP_KEY"):
        resolve_connection(env={"DD_API_KEY": "api-key"})


def test_the_environment_is_read_from_the_process_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DD_API_KEY", "from-process")
    monkeypatch.setenv("DD_APP_KEY", "app-key")
    monkeypatch.delenv("DD_SITE", raising=False)

    assert resolve_connection().api_key == "from-process"
