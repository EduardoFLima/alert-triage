from datetime import timedelta
from pathlib import Path

import pytest

from alert_triage.adapters.config.yaml_env import YamlEnvConfig
from alert_triage.ports.config import Config, ConfigurationError

TEAM_ENV = {"SCOPE_DATADOG_TEAM": "platform"}


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    return tmp_path / "config.yaml"


def write(config_file: Path, body: str) -> Path:
    config_file.write_text(body)
    return config_file


def test_a_missing_config_file_is_not_an_error(config_file: Path) -> None:
    assert not config_file.exists()

    config = YamlEnvConfig(config_path=config_file, environ=TEAM_ENV)

    assert config.scope.datadog_team == "platform"


def test_the_adapter_satisfies_the_config_port(config_file: Path) -> None:
    config: Config = YamlEnvConfig(config_path=config_file, environ=TEAM_ENV)

    assert isinstance(config, Config)


def test_omitted_circuit_breakers_resolve_to_the_documented_defaults(
    config_file: Path,
) -> None:
    write(config_file, "scope:\n  datadog_team: platform\n")

    config = YamlEnvConfig(config_path=config_file, environ={})

    assert config.circuit_breakers.max_tool_calls_per_agent == 8
    assert config.circuit_breakers.max_agent_hops == 2
    assert config.circuit_breakers.max_investigation_duration_seconds == 120
    assert config.circuit_breakers.max_mcp_retries == 3
    assert config.circuit_breakers.mcp_call_timeout_seconds == 30


def test_a_specified_circuit_breaker_leaves_its_siblings_on_their_defaults(
    config_file: Path,
) -> None:
    write(
        config_file,
        "scope:\n  datadog_team: platform\ncircuit_breakers:\n  max_agent_hops: 5\n",
    )

    config = YamlEnvConfig(config_path=config_file, environ={})

    assert config.circuit_breakers.max_agent_hops == 5
    assert config.circuit_breakers.max_tool_calls_per_agent == 8


def test_omitted_critical_services_gets_no_default_whatsoever(
    config_file: Path,
) -> None:
    write(config_file, "scope:\n  datadog_team: platform\n")

    config = YamlEnvConfig(config_path=config_file, environ={})

    assert config.critical_services == {}


def test_a_partially_specified_service_leaves_its_other_keys_unresolved(
    config_file: Path,
) -> None:
    write(
        config_file,
        "scope:\n"
        "  datadog_team: platform\n"
        "critical_services:\n"
        "  checkout:\n"
        "    tier: gold\n",
    )

    config = YamlEnvConfig(config_path=config_file, environ={})

    assert config.critical_services == {"checkout": {"tier": "gold"}}
    assert "latency_threshold_ms" not in config.critical_services["checkout"]


def test_scope_resolves_from_the_config_file_alone(config_file: Path) -> None:
    write(config_file, "scope:\n  datadog_team: from-file\n")

    config = YamlEnvConfig(config_path=config_file, environ={})

    assert config.scope.datadog_team == "from-file"


def test_scope_resolves_from_the_environment_alone(config_file: Path) -> None:
    config = YamlEnvConfig(
        config_path=config_file, environ={"SCOPE_DATADOG_TEAM": "from-env"}
    )

    assert config.scope.datadog_team == "from-env"


def test_scope_missing_from_both_sources_refuses_to_start(config_file: Path) -> None:
    write(config_file, "circuit_breakers:\n  max_agent_hops: 5\n")

    with pytest.raises(ConfigurationError, match="SCOPE_DATADOG_TEAM"):
        YamlEnvConfig(config_path=config_file, environ={})


def test_the_environment_wins_over_the_config_file_for_scope(
    config_file: Path,
) -> None:
    write(config_file, "scope:\n  datadog_team: from-file\n")

    config = YamlEnvConfig(
        config_path=config_file, environ={"SCOPE_DATADOG_TEAM": "from-env"}
    )

    assert config.scope.datadog_team == "from-env"


def test_the_environment_wins_over_the_config_file_beyond_scope(
    config_file: Path,
) -> None:
    write(
        config_file,
        "scope:\n  datadog_team: platform\ncircuit_breakers:\n  max_mcp_retries: 7\n",
    )

    config = YamlEnvConfig(
        config_path=config_file,
        environ={**TEAM_ENV, "CIRCUIT_BREAKERS_MAX_MCP_RETRIES": "9"},
    )

    assert config.circuit_breakers.max_mcp_retries == 9


def test_an_environment_override_applies_inside_critical_services(
    config_file: Path,
) -> None:
    write(
        config_file,
        "scope:\n"
        "  datadog_team: platform\n"
        "critical_services:\n"
        "  checkout:\n"
        "    tier: gold\n",
    )

    config = YamlEnvConfig(
        config_path=config_file,
        environ={"CRITICAL_SERVICES_CHECKOUT_TIER": "silver"},
    )

    assert config.critical_services["checkout"]["tier"] == "silver"


def test_the_grouping_window_has_a_documented_default(config_file: Path) -> None:
    config = YamlEnvConfig(config_path=config_file, environ=TEAM_ENV)

    assert config.grouping.window == timedelta(minutes=5)


def test_the_grouping_window_resolves_from_the_config_file(config_file: Path) -> None:
    write(
        config_file,
        "scope:\n  datadog_team: platform\ngrouping:\n  window_seconds: 60\n",
    )

    config = YamlEnvConfig(config_path=config_file, environ={})

    assert config.grouping.window == timedelta(seconds=60)


def test_the_grouping_window_resolves_from_the_environment(config_file: Path) -> None:
    config = YamlEnvConfig(
        config_path=config_file,
        environ={**TEAM_ENV, "GROUPING_WINDOW_SECONDS": "45"},
    )

    assert config.grouping.window == timedelta(seconds=45)


def test_a_non_numeric_override_of_a_numeric_value_is_reported(
    config_file: Path,
) -> None:
    with pytest.raises(ConfigurationError, match="GROUPING_WINDOW_SECONDS"):
        YamlEnvConfig(
            config_path=config_file,
            environ={**TEAM_ENV, "GROUPING_WINDOW_SECONDS": "soon"},
        )


def test_an_empty_config_file_resolves_like_a_missing_one(config_file: Path) -> None:
    write(config_file, "")

    config = YamlEnvConfig(config_path=config_file, environ=TEAM_ENV)

    assert config.scope.datadog_team == "platform"
    assert config.critical_services == {}


def test_a_malformed_config_file_is_reported_as_a_configuration_problem(
    config_file: Path,
) -> None:
    write(config_file, "scope: [unclosed\n")

    with pytest.raises(ConfigurationError, match="not valid YAML"):
        YamlEnvConfig(config_path=config_file, environ=TEAM_ENV)


def test_a_config_file_that_is_not_a_mapping_is_reported(config_file: Path) -> None:
    write(config_file, "- platform\n")

    with pytest.raises(ConfigurationError, match="mapping of sections"):
        YamlEnvConfig(config_path=config_file, environ=TEAM_ENV)


def test_critical_services_that_is_not_a_mapping_is_reported(
    config_file: Path,
) -> None:
    write(config_file, "critical_services:\n  - checkout\n")

    with pytest.raises(ConfigurationError, match="map service names"):
        YamlEnvConfig(config_path=config_file, environ=TEAM_ENV)


def test_a_service_entry_that_is_not_a_mapping_is_reported(config_file: Path) -> None:
    write(config_file, "critical_services:\n  checkout: gold\n")

    with pytest.raises(ConfigurationError, match=r"critical_services\.checkout"):
        YamlEnvConfig(config_path=config_file, environ=TEAM_ENV)
