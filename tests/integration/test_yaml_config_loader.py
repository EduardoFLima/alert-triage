from datetime import timedelta
from pathlib import Path

import pytest

from alert_triage.adapters.datadog.connection import resolve_connection
from alert_triage.adapters.sqlite_ledger import (
    DEFAULT_LEDGER_PATH,
    resolve_ledger_path,
)
from alert_triage.adapters.yaml_config import load_config
from alert_triage.ports.config import Config, ConfigError, CriticalService

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

    assert config.circuit_breakers.max_tool_calls_per_agent == 8
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
    assert config.circuit_breakers.max_tool_calls_per_agent == 8


def test_omitting_critical_services_means_no_service_is_critical(
    tmp_path: Path,
) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={})

    assert config.critical_services == {}


def test_a_partially_specified_critical_service_keeps_defaults_for_the_rest(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
critical_services:
  checkout:
    latency_threshold_ms: 250
  payments: {}
""",
    )

    config = load_config(path, env={})

    assert set(config.critical_services) == {"checkout", "payments"}
    assert config.critical_services["checkout"].latency_threshold_ms == 250
    assert config.critical_services["checkout"].tier == CriticalService.DEFAULT_TIER
    assert config.critical_services["payments"] == CriticalService()


def test_scope_resolves_from_the_config_file_alone(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={})

    assert config.scope.owner == "sre"


def test_scope_resolves_from_the_environment_alone(tmp_path: Path) -> None:
    path = _write(tmp_path, "circuit_breakers:\n  max_agent_hops: 4\n")

    config = load_config(path, env={"SCOPE_OWNER": "platform"})

    assert config.scope.owner == "platform"


def test_scope_missing_from_both_sources_refuses_to_start(tmp_path: Path) -> None:
    path = _write(tmp_path, "circuit_breakers:\n  max_agent_hops: 4\n")

    with pytest.raises(ConfigError, match=r"scope\.owner"):
        load_config(path, env={})


def test_environment_wins_over_the_file_for_scope(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={"SCOPE_OWNER": "platform"})

    assert config.scope.owner == "platform"


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


def test_environment_overrides_a_declared_critical_service_threshold(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
critical_services:
  checkout:
    latency_threshold_ms: 250
""",
    )

    config = load_config(path, env={"CRITICAL_SERVICES_CHECKOUT_TIER": "tier-1"})

    assert config.critical_services["checkout"].tier == "tier-1"
    assert config.critical_services["checkout"].latency_threshold_ms == 250


def test_the_environment_is_read_from_the_process_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCOPE_OWNER", "from-process")

    config = load_config(tmp_path / "absent.yaml")

    assert config.scope.owner == "from-process"


def test_grouping_window_defaults_and_is_configurable(tmp_path: Path) -> None:
    default = load_config(_write(tmp_path, SCOPED), env={})

    assert default.grouping.window == timedelta(minutes=30)

    from_file = load_config(
        _write(tmp_path, SCOPED + "\ngrouping:\n  window_seconds: 900\n"), env={}
    )

    assert from_file.grouping.window == timedelta(minutes=15)

    from_env = load_config(
        _write(tmp_path, SCOPED + "\ngrouping:\n  window_seconds: 900\n"),
        env={"GROUPING_WINDOW_SECONDS": "60"},
    )

    assert from_env.grouping.window == timedelta(minutes=1)


def test_ingestion_lookback_defaults_and_is_configurable(tmp_path: Path) -> None:
    default = load_config(_write(tmp_path, SCOPED), env={})

    assert default.ingestion.lookback == timedelta(hours=1)

    from_file = load_config(
        _write(tmp_path, SCOPED + "\ningestion:\n  lookback_seconds: 900\n"), env={}
    )

    assert from_file.ingestion.lookback == timedelta(minutes=15)

    from_env = load_config(
        _write(tmp_path, SCOPED + "\ningestion:\n  lookback_seconds: 900\n"),
        env={"INGESTION_LOOKBACK_SECONDS": "60"},
    )

    assert from_env.ingestion.lookback == timedelta(minutes=1)


def test_ingestion_request_bounds_fall_back_to_documented_defaults(
    tmp_path: Path,
) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={})

    assert config.ingestion.request_timeout_seconds == 30
    assert config.ingestion.max_retries == 3


def test_changing_an_investigation_breaker_leaves_ingestion_unchanged(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
circuit_breakers:
  mcp_call_timeout_seconds: 90
  max_mcp_retries: 9
""",
    )

    config = load_config(path, env={})

    assert config.ingestion.request_timeout_seconds == 30
    assert config.ingestion.max_retries == 3


def test_changing_an_ingestion_bound_leaves_the_breakers_unchanged(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
ingestion:
  request_timeout_seconds: 90
  max_retries: 9
""",
    )

    config = load_config(path, env={"INGESTION_MAX_RETRIES": "5"})

    assert config.ingestion.request_timeout_seconds == 90
    assert config.ingestion.max_retries == 5
    assert config.circuit_breakers.mcp_call_timeout_seconds == 30
    assert config.circuit_breakers.max_mcp_retries == 3


CONNECTION_KEYS_IN_FILE = """
datadog:
  site: datadoghq.eu
  api_key: from-the-file
  app_key: from-the-file
"""


def test_connection_keys_in_the_file_are_not_used_to_reach_the_platform(
    tmp_path: Path,
) -> None:
    """`config.yaml` is behavior only; a site or credential written there is inert."""
    path = _write(tmp_path, SCOPED + CONNECTION_KEYS_IN_FILE)

    config = load_config(path, env={})

    assert config.scope.owner == "sre"
    assert not hasattr(config, "datadog")

    with pytest.raises(ConfigError, match="DD_API_KEY"):
        resolve_connection(env={})


def test_behavior_keys_beside_connection_keys_still_resolve(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        SCOPED + CONNECTION_KEYS_IN_FILE + "\ningestion:\n  lookback_seconds: 120\n",
    )

    config = load_config(path, env={"INGESTION_LOOKBACK_SECONDS": "60"})

    assert config.ingestion.lookback == timedelta(minutes=1)


def test_an_unknown_config_key_is_reported_rather_than_ignored(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\ncircuit_breakers:\n  max_agent_hopz: 5\n")

    with pytest.raises(ConfigError, match="max_agent_hopz"):
        load_config(path, env={})


def test_an_empty_config_file_is_treated_as_no_settings(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, ""), env={"SCOPE_OWNER": "sre"})

    assert config.circuit_breakers.max_agent_hops == 2


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


def test_a_critical_service_entry_that_is_not_a_mapping_is_rejected(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\ncritical_services:\n  checkout: tier-1\n")

    with pytest.raises(ConfigError, match=r"critical_services\.checkout"):
        load_config(path, env={})


def test_a_critical_service_listed_with_no_thresholds_is_still_critical(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\ncritical_services:\n  checkout:\n")

    config = load_config(path, env={})

    assert config.critical_services == {"checkout": CriticalService()}


def test_a_non_numeric_override_names_the_offending_variable(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED)

    with pytest.raises(ConfigError, match="CIRCUIT_BREAKERS_MAX_AGENT_HOPS"):
        load_config(path, env={"CIRCUIT_BREAKERS_MAX_AGENT_HOPS": "many"})


def test_the_cooldown_falls_back_to_the_documented_default(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={})

    assert config.re_notify.cooldown == timedelta(days=2)


def test_the_cooldown_is_taken_from_the_file_when_only_the_file_sets_it(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\nre_notify:\n  cooldown_seconds: 3600\n")

    config = load_config(path, env={})

    assert config.re_notify.cooldown == timedelta(hours=1)


def test_the_environment_wins_over_the_file_for_the_cooldown(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\nre_notify:\n  cooldown_seconds: 3600\n")

    config = load_config(path, env={"RE_NOTIFY_COOLDOWN_SECONDS": "60"})

    assert config.re_notify.cooldown == timedelta(minutes=1)


def test_retention_falls_back_to_the_documented_thirty_days(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={})

    assert config.ledger.retention == timedelta(days=30)


def test_retention_is_taken_from_the_operator(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\nledger:\n  retention_seconds: 86400\n")

    config = load_config(path, env={"LEDGER_RETENTION_SECONDS": "3600"})

    assert config.ledger.retention == timedelta(hours=1)


def test_setting_the_cooldown_leaves_the_resolved_retention_alone(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\nre_notify:\n  cooldown_seconds: 60\n")

    config = load_config(path, env={})

    assert config.ledger.retention == timedelta(days=30)


def test_setting_retention_leaves_the_resolved_cooldown_alone(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\nledger:\n  retention_seconds: 60\n")

    config = load_config(path, env={})

    assert config.re_notify.cooldown == timedelta(days=2)


LEDGER_LOCATION_IN_FILE = """
ledger_storage:
  path: /from/the/file.db
"""


def test_a_ledger_location_in_the_file_is_not_where_records_are_kept(
    tmp_path: Path,
) -> None:
    """Where a database lives is a deployment fact; `config.yaml` is behavior."""
    path = _write(tmp_path, SCOPED + LEDGER_LOCATION_IN_FILE)

    config = load_config(path, env={})

    assert not hasattr(config, "ledger_storage")
    assert resolve_ledger_path(env={}) == DEFAULT_LEDGER_PATH
