from dataclasses import dataclass, field
from datetime import timedelta

from alert_triage.domain.config import CircuitBreakers, GroupingSettings, Scope
from alert_triage.ports.config import Config


@dataclass(frozen=True)
class StubConfig:
    """The in-memory config a consumer's tests substitute for the adapter."""

    scope: Scope = field(default_factory=lambda: Scope(datadog_team="platform"))
    circuit_breakers: CircuitBreakers = field(default_factory=CircuitBreakers)
    grouping: GroupingSettings = field(default_factory=GroupingSettings)
    critical_services: dict[str, dict[str, object]] = field(default_factory=dict)


def test_an_in_memory_config_satisfies_the_port() -> None:
    config: Config = StubConfig()

    assert isinstance(config, Config)


def test_the_port_exposes_the_values_consumers_resolve_against() -> None:
    config: Config = StubConfig()

    assert config.scope.datadog_team == "platform"
    assert config.circuit_breakers.max_agent_hops == 2
    assert config.grouping.window == timedelta(minutes=5)
    assert config.critical_services == {}


def test_an_object_missing_a_config_value_does_not_satisfy_the_port() -> None:
    @dataclass(frozen=True)
    class ScopeOnly:
        scope: Scope = field(default_factory=lambda: Scope(datadog_team="platform"))

    assert not isinstance(ScopeOnly(), Config)


def test_circuit_breaker_defaults_match_the_documented_thresholds() -> None:
    breakers = CircuitBreakers()

    assert breakers.max_tool_calls_per_agent == 8
    assert breakers.max_agent_hops == 2
    assert breakers.max_investigation_duration_seconds == 120
    assert breakers.max_mcp_retries == 3
    assert breakers.mcp_call_timeout_seconds == 30


def test_the_grouping_window_is_expressed_as_a_duration() -> None:
    assert GroupingSettings(window_seconds=90).window == timedelta(seconds=90)
