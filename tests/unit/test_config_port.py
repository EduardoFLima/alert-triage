from dataclasses import dataclass, field
from datetime import timedelta

from alert_triage.ports.config import (
    CircuitBreakers,
    Config,
    CriticalService,
    Grouping,
    Scope,
)


@dataclass(frozen=True)
class InMemoryConfig:
    """What a test double for the port looks like: values, no source."""

    scope: Scope
    grouping: Grouping = field(default_factory=Grouping)
    circuit_breakers: CircuitBreakers = field(default_factory=CircuitBreakers)
    critical_services: dict[str, CriticalService] = field(default_factory=dict)


def test_an_in_memory_implementation_satisfies_the_port() -> None:
    config: Config = InMemoryConfig(scope=Scope(datadog_team="sre"))

    assert isinstance(config, Config)
    assert config.scope.datadog_team == "sre"


def test_circuit_breaker_defaults_match_the_documented_thresholds() -> None:
    breakers = CircuitBreakers()

    assert breakers.max_tool_calls_per_agent == 8
    assert breakers.max_agent_hops == 2
    assert breakers.max_investigation_duration_seconds == 120
    assert breakers.max_mcp_retries == 3
    assert breakers.mcp_call_timeout_seconds == 30


def test_grouping_window_is_offered_to_the_domain_as_a_duration() -> None:
    assert Grouping(window_seconds=600).window == timedelta(minutes=10)
    assert Grouping().window == timedelta(seconds=Grouping.DEFAULT_WINDOW_SECONDS)


def test_critical_service_thresholds_have_documented_defaults() -> None:
    service = CriticalService()

    assert service.tier == CriticalService.DEFAULT_TIER
    assert service.latency_threshold_ms == CriticalService.DEFAULT_LATENCY_THRESHOLD_MS


def test_no_service_is_critical_unless_the_config_says_so() -> None:
    config: Config = InMemoryConfig(scope=Scope(datadog_team="sre"))

    assert config.critical_services == {}
