from datetime import timedelta
from pathlib import Path

import pytest

from alert_triage.configuration.adapters.yaml import load_config
from alert_triage.configuration.port import Config, ConfigError
from alert_triage.configuration.settings import CircuitBreakers, ServiceScope
from alert_triage.triage.adapters.datadog.connection import resolve_connection
from alert_triage.triage.adapters.sqlite import (
    DEFAULT_LEDGER_PATH,
    resolve_ledger_path,
)

SCOPED = """
scope:
  owner: sre
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(body)
    return path


def test_missing_config_file_is_not_an_error(tmp_path: Path) -> None:
    config = load_config(tmp_path / "absent.yaml", env={"SCOPE_OWNER": "sre"})

    assert config.scope.owner == "sre"


def test_loaded_config_satisfies_the_port(tmp_path: Path) -> None:
    config: Config = load_config(_write(tmp_path, SCOPED), env={})

    assert isinstance(config, Config)


def test_circuit_breakers_fall_back_to_documented_defaults(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={})

    assert config.circuit_breakers.max_tool_calls_per_agent == 12
    assert config.circuit_breakers.mcp_call_timeout_seconds == 30


def test_circuit_breakers_keep_the_keys_the_file_does_set(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
circuit_breakers:
  max_agent_hops: 5
""",
    )

    config = load_config(path, env={})

    assert config.circuit_breakers.max_agent_hops == 5
    assert config.circuit_breakers.max_tool_calls_per_agent == 12


def test_the_services_the_file_names_are_the_services_in_scope(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
  services:
    checkout: {}
    payments:
""",
    )

    config = load_config(path, env={})

    assert set(config.scope.services) == {"checkout", "payments"}


def test_a_service_listed_with_no_settings_is_in_scope_and_not_critical(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\n  services:\n    checkout:\n")

    config = load_config(path, env={})

    assert config.scope.services["checkout"] == ServiceScope()
    assert not config.scope.services["checkout"].critical


def test_a_service_the_file_declares_critical_resolves_as_critical(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
  services:
    checkout:
      critical: true
    payments: {}
""",
    )

    config = load_config(path, env={})

    assert config.scope.services["checkout"].critical
    assert not config.scope.services["payments"].critical


def test_a_service_entry_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\n  services:\n    checkout: critical\n")

    with pytest.raises(ConfigError, match=r"scope\.services\.checkout"):
        load_config(path, env={})


def test_an_unknown_key_within_a_service_entry_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\n  services:\n    checkout:\n      tier: 1\n")

    with pytest.raises(ConfigError, match="tier"):
        load_config(path, env={})


def test_services_alone_satisfy_scope(tmp_path: Path) -> None:
    path = _write(tmp_path, "scope:\n  services:\n    checkout: {}\n")

    config = load_config(path, env={})

    assert config.scope.owner is None
    assert set(config.scope.services) == {"checkout"}


def test_neither_owner_nor_services_refuses_to_start(tmp_path: Path) -> None:
    path = _write(tmp_path, "circuit_breakers:\n  max_agent_hops: 4\n")

    with pytest.raises(ConfigError, match=r"scope\.owner.*scope\.services"):
        load_config(path, env={})


def test_an_empty_services_mapping_does_not_satisfy_scope(tmp_path: Path) -> None:
    path = _write(tmp_path, "scope:\n  services: {}\n")

    with pytest.raises(ConfigError, match=r"scope\.services"):
        load_config(path, env={})


def test_the_environment_alone_declares_the_services_in_scope(
    tmp_path: Path,
) -> None:
    config = load_config(
        tmp_path / "absent.yaml", env={"SCOPE_SERVICES": "checkout,payments"}
    )

    assert set(config.scope.services) == {"checkout", "payments"}
    assert not any(service.critical for service in config.scope.services.values())


def test_the_environment_replaces_the_files_services_rather_than_merging(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
  services:
    checkout:
      critical: true
""",
    )

    config = load_config(path, env={"SCOPE_SERVICES": "payments"})

    assert set(config.scope.services) == {"payments"}
    assert not config.scope.services["payments"].critical


def test_a_service_declared_from_the_environment_is_declared_critical_there(
    tmp_path: Path,
) -> None:
    config = load_config(
        tmp_path / "absent.yaml",
        env={
            "SCOPE_SERVICES": "checkout,payments",
            "SCOPE_SERVICES_CHECKOUT_CRITICAL": "true",
        },
    )

    assert config.scope.services["checkout"].critical
    assert not config.scope.services["payments"].critical


def test_a_service_the_file_declared_is_declared_critical_from_the_environment(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\n  services:\n    checkout: {}\n")

    config = load_config(path, env={"SCOPE_SERVICES_CHECKOUT_CRITICAL": "true"})

    assert config.scope.services["checkout"].critical


def test_a_criticality_that_is_neither_yes_nor_no_names_the_variable(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\n  services:\n    checkout: {}\n")

    with pytest.raises(ConfigError, match="SCOPE_SERVICES_CHECKOUT_CRITICAL"):
        load_config(path, env={"SCOPE_SERVICES_CHECKOUT_CRITICAL": "maybe"})


def test_the_environment_can_stand_a_service_down_from_critical(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
  services:
    checkout:
      critical: true
""",
    )

    config = load_config(path, env={"SCOPE_SERVICES_CHECKOUT_CRITICAL": "false"})

    assert not config.scope.services["checkout"].critical


def test_the_files_services_stand_when_the_environment_declares_none(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
  services:
    checkout:
      critical: true
    payments: {}
""",
    )

    config = load_config(path, env={})

    assert set(config.scope.services) == {"checkout", "payments"}
    assert config.scope.services["checkout"].critical


def test_scope_owner_resolves_from_file_environment_and_environment_wins(
    tmp_path: Path,
) -> None:
    from_file = load_config(_write(tmp_path, SCOPED), env={})
    from_environment = load_config(
        _write(tmp_path, "circuit_breakers:\n  max_agent_hops: 4\n"),
        env={"SCOPE_OWNER": "platform"},
    )
    environment_override = load_config(
        _write(tmp_path, SCOPED), env={"SCOPE_OWNER": "platform"}
    )

    assert from_file.scope.owner == "sre"
    assert from_environment.scope.owner == "platform"
    assert environment_override.scope.owner == "platform"


def test_scope_environment_defaults_resolves_and_environment_wins(
    tmp_path: Path,
) -> None:
    default = load_config(_write(tmp_path, SCOPED), env={})
    from_file = load_config(_write(tmp_path, SCOPED + "  env: staging\n"), env={})
    from_environment = load_config(
        _write(tmp_path, SCOPED), env={"SCOPE_ENV": "staging"}
    )
    environment_override = load_config(
        _write(tmp_path, SCOPED + "  env: staging\n"), env={"SCOPE_ENV": "prod"}
    )

    assert default.scope.env == "prod"
    assert from_file.scope.env == "staging"
    assert from_environment.scope.env == "staging"
    assert environment_override.scope.env == "prod"


def test_an_environment_alone_does_not_satisfy_scope(tmp_path: Path) -> None:
    path = _write(tmp_path, "scope:\n  env: prod\n")

    with pytest.raises(ConfigError, match="requires an owner, services, or both"):
        load_config(path, env={})


def test_scope_env_alone_does_not_satisfy_scope(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="requires an owner, services, or both"):
        load_config(tmp_path / "absent.yaml", env={"SCOPE_ENV": "prod"})


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_environment_in_the_file_is_refused_by_name(
    tmp_path: Path, blank: str
) -> None:
    path = _write(tmp_path, SCOPED + f"  env: '{blank}'\n")

    with pytest.raises(ConfigError, match=r"scope\.env"):
        load_config(path, env={})


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_scope_env_is_refused_by_name(tmp_path: Path, blank: str) -> None:
    with pytest.raises(ConfigError, match="SCOPE_ENV"):
        load_config(_write(tmp_path, SCOPED), env={"SCOPE_ENV": blank})


def test_environment_wins_over_the_file_for_any_other_value(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
circuit_breakers:
  max_agent_hops: 5
""",
    )

    config = load_config(path, env={"CIRCUIT_BREAKERS_MAX_AGENT_HOPS": "9"})

    assert config.circuit_breakers.max_agent_hops == 9


def test_the_environment_is_read_from_the_process_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCOPE_OWNER", "from-process")

    config = load_config(tmp_path / "absent.yaml")

    assert config.scope.owner == "from-process"


def test_duration_settings_default_resolve_from_file_and_environment(
    tmp_path: Path,
) -> None:
    cases = (
        (
            "grouping",
            "window",
            "\ngrouping:\n  window_seconds: 900\n",
            "GROUPING_WINDOW_SECONDS",
            timedelta(minutes=30),
            timedelta(minutes=15),
            timedelta(minutes=1),
        ),
        (
            "ingestion",
            "lookback",
            "\ningestion:\n  lookback_seconds: 900\n",
            "INGESTION_LOOKBACK_SECONDS",
            timedelta(hours=1),
            timedelta(minutes=15),
            timedelta(minutes=1),
        ),
    )

    for (
        section,
        attribute,
        yaml,
        variable,
        expected_default,
        expected_file,
        expected_env,
    ) in cases:
        default = load_config(_write(tmp_path, SCOPED), env={})
        from_file = load_config(_write(tmp_path, SCOPED + yaml), env={})
        from_env = load_config(_write(tmp_path, SCOPED + yaml), env={variable: "60"})

        assert getattr(getattr(default, section), attribute) == expected_default
        assert getattr(getattr(from_file, section), attribute) == expected_file
        assert getattr(getattr(from_env, section), attribute) == expected_env


def test_ingestion_request_bounds_fall_back_to_documented_defaults(
    tmp_path: Path,
) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={})

    assert config.ingestion.request_timeout_seconds == 30
    assert config.ingestion.max_retries == 3


def test_ingestion_bounds_and_investigation_breakers_resolve_independently(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
circuit_breakers:
  mcp_call_timeout_seconds: 90
  max_tool_calls_per_agent: 9
""",
    )

    breakers_changed = load_config(path, env={})

    ingestion_path = _write(
        tmp_path,
        SCOPED
        + """
ingestion:
  request_timeout_seconds: 90
  max_retries: 9
""",
    )
    ingestion_changed = load_config(ingestion_path, env={"INGESTION_MAX_RETRIES": "5"})

    assert breakers_changed.ingestion.request_timeout_seconds == 30
    assert breakers_changed.ingestion.max_retries == 3
    assert ingestion_changed.ingestion.request_timeout_seconds == 90
    assert ingestion_changed.ingestion.max_retries == 5
    assert ingestion_changed.circuit_breakers.mcp_call_timeout_seconds == 30
    assert ingestion_changed.circuit_breakers.max_tool_calls_per_agent == 12


CONNECTION_KEYS_IN_FILE = """
datadog:
  site: datadoghq.eu
  api_key: from-the-file
  app_key: from-the-file
"""


def test_connection_keys_in_the_file_are_refused_rather_than_read(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + CONNECTION_KEYS_IN_FILE)

    with pytest.raises(ConfigError, match="datadog"):
        load_config(path, env={})

    with pytest.raises(ConfigError, match="DD_API_KEY"):
        resolve_connection(env={})


def test_an_unknown_config_key_is_reported_rather_than_ignored(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\ncircuit_breakers:\n  max_agent_hopz: 5\n")

    with pytest.raises(ConfigError, match="max_agent_hopz"):
        load_config(path, env={})


def test_a_config_still_declaring_max_mcp_retries_is_refused(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\ncircuit_breakers:\n  max_mcp_retries: 5\n")

    with pytest.raises(ConfigError, match="max_mcp_retries"):
        load_config(path, env={})


def test_the_retired_retry_key_has_no_environment_override_either(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED)

    config = load_config(
        path,
        env={
            "CIRCUIT_BREAKERS_MAX_MCP_RETRIES": "9",
            "MAX_MCP_RETRIES": "9",
        },
    )

    assert not hasattr(config.circuit_breakers, "max_mcp_retries")
    assert config.circuit_breakers == CircuitBreakers()


def test_a_config_still_declaring_critical_services_is_refused(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\ncritical_services:\n  checkout: {}\n")

    with pytest.raises(ConfigError, match="critical_services"):
        load_config(path, env={})


def test_an_unknown_config_section_is_reported_rather_than_ignored(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\nscoop:\n  owner: sre\n")

    with pytest.raises(ConfigError, match="scoop"):
        load_config(path, env={})


def test_an_empty_config_file_is_treated_as_no_settings(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, ""), env={"SCOPE_OWNER": "sre"})

    assert config.circuit_breakers.max_agent_hops == 8


def test_unparseable_yaml_is_reported_as_a_config_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "scope: [unclosed\n")

    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(path, env={})


def test_a_config_file_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, "- sre\n")

    with pytest.raises(ConfigError, match="mapping of config sections"):
        load_config(path, env={})


def test_a_section_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, "scope: sre\n")

    with pytest.raises(ConfigError, match="'scope' must be a mapping"):
        load_config(path, env={})


def test_a_non_numeric_override_names_the_offending_variable(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED)

    with pytest.raises(ConfigError, match="CIRCUIT_BREAKERS_MAX_AGENT_HOPS"):
        load_config(path, env={"CIRCUIT_BREAKERS_MAX_AGENT_HOPS": "many"})


def test_notification_cooldown_and_ledger_retention_resolve_as_durations(
    tmp_path: Path,
) -> None:
    cases = (
        (
            "re_notify",
            "cooldown",
            "\nre_notify:\n  cooldown_seconds: 3600\n",
            "RE_NOTIFY_COOLDOWN_SECONDS",
            timedelta(days=2),
            timedelta(hours=1),
            "60",
            timedelta(minutes=1),
        ),
        (
            "ledger",
            "retention",
            "\nledger:\n  retention_seconds: 86400\n",
            "LEDGER_RETENTION_SECONDS",
            timedelta(days=30),
            timedelta(days=1),
            "3600",
            timedelta(hours=1),
        ),
    )

    for (
        section,
        attribute,
        yaml,
        variable,
        expected_default,
        expected_file,
        env_value,
        expected_env,
    ) in cases:
        default = load_config(_write(tmp_path, SCOPED), env={})
        from_file = load_config(_write(tmp_path, SCOPED + yaml), env={})
        from_env = load_config(
            _write(tmp_path, SCOPED + yaml), env={variable: env_value}
        )

        assert getattr(getattr(default, section), attribute) == expected_default
        assert getattr(getattr(from_file, section), attribute) == expected_file
        assert getattr(getattr(from_env, section), attribute) == expected_env


def test_cooldown_and_retention_do_not_change_each_other(tmp_path: Path) -> None:
    cooldown_changed = load_config(
        _write(tmp_path, SCOPED + "\nre_notify:\n  cooldown_seconds: 60\n"), env={}
    )
    retention_changed = load_config(
        _write(tmp_path, SCOPED + "\nledger:\n  retention_seconds: 60\n"), env={}
    )

    assert cooldown_changed.ledger.retention == timedelta(days=30)
    assert retention_changed.re_notify.cooldown == timedelta(days=2)


LEDGER_LOCATION_IN_FILE = """
ledger_storage:
  path: /from/the/file.db
"""


def test_a_ledger_location_in_the_file_is_not_where_records_are_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    path = _write(tmp_path, SCOPED + LEDGER_LOCATION_IN_FILE)

    with pytest.raises(ConfigError, match="ledger_storage"):
        load_config(path, env={})

    assert resolve_ledger_path(env={}) == DEFAULT_LEDGER_PATH
