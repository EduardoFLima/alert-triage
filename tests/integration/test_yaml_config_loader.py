from datetime import timedelta
from pathlib import Path

import pytest

from alert_triage.adapters.yaml_config import load_config
from alert_triage.ports.config import Config, ConfigError, CriticalService

SCOPED = """
scope:
  datadog_team: sre
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(body)
    return path


def test_missing_config_file_is_not_an_error(tmp_path: Path) -> None:
    config = load_config(tmp_path / "absent.yaml", env={"SCOPE_DATADOG_TEAM": "sre"})

    assert config.scope.datadog_team == "sre"


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

    assert config.scope.datadog_team == "sre"


def test_scope_resolves_from_the_environment_alone(tmp_path: Path) -> None:
    path = _write(tmp_path, "circuit_breakers:\n  max_agent_hops: 4\n")

    config = load_config(path, env={"SCOPE_DATADOG_TEAM": "platform"})

    assert config.scope.datadog_team == "platform"


def test_scope_missing_from_both_sources_refuses_to_start(tmp_path: Path) -> None:
    path = _write(tmp_path, "circuit_breakers:\n  max_agent_hops: 4\n")

    with pytest.raises(ConfigError, match=r"scope\.datadog_team"):
        load_config(path, env={})


def test_environment_wins_over_the_file_for_scope(tmp_path: Path) -> None:
    config = load_config(
        _write(tmp_path, SCOPED), env={"SCOPE_DATADOG_TEAM": "platform"}
    )

    assert config.scope.datadog_team == "platform"


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
    monkeypatch.setenv("SCOPE_DATADOG_TEAM", "from-process")

    config = load_config(tmp_path / "absent.yaml")

    assert config.scope.datadog_team == "from-process"


def test_grouping_window_defaults_and_is_configurable(tmp_path: Path) -> None:
    default = load_config(_write(tmp_path, SCOPED), env={})

    assert default.grouping.window == timedelta(minutes=5)

    from_file = load_config(
        _write(tmp_path, SCOPED + "\ngrouping:\n  window_seconds: 900\n"), env={}
    )

    assert from_file.grouping.window == timedelta(minutes=15)

    from_env = load_config(
        _write(tmp_path, SCOPED + "\ngrouping:\n  window_seconds: 900\n"),
        env={"GROUPING_WINDOW_SECONDS": "60"},
    )

    assert from_env.grouping.window == timedelta(minutes=1)


def test_an_unknown_config_key_is_reported_rather_than_ignored(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCOPED + "\ncircuit_breakers:\n  max_agent_hopz: 5\n")

    with pytest.raises(ConfigError, match="max_agent_hopz"):
        load_config(path, env={})


def test_an_empty_config_file_is_treated_as_no_settings(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, ""), env={"SCOPE_DATADOG_TEAM": "sre"})

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
