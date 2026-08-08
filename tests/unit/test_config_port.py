from dataclasses import dataclass, field
from datetime import timedelta

from alert_triage.ports.config import (
    CircuitBreakers,
    Config,
    CriticalService,
    Grouping,
    Ingestion,
    Scope,
)


@dataclass(frozen=True)
class InMemoryConfig:
    """What a test double for the port looks like: values, no source."""

    scope: Scope
    grouping: Grouping = field(default_factory=Grouping)
    ingestion: Ingestion = field(default_factory=Ingestion)
    circuit_breakers: CircuitBreakers = field(default_factory=CircuitBreakers)
    critical_services: dict[str, CriticalService] = field(default_factory=dict)


def test_an_in_memory_implementation_satisfies_the_port() -> None:
    config: Config = InMemoryConfig(scope=Scope(owner="sre"))

    assert isinstance(config, Config)
    assert config.scope.owner == "sre"


def test_circuit_breaker_defaults_match_the_documented_thresholds() -> None:
    breakers = CircuitBreakers()

    assert breakers.max_tool_calls_per_agent == 8
    assert breakers.max_agent_hops == 2
    assert breakers.max_investigation_duration_seconds == 300
    assert breakers.max_mcp_retries == 3
    assert breakers.mcp_call_timeout_seconds == 30


def test_grouping_window_is_offered_to_the_domain_as_a_duration() -> None:
    assert Grouping(window_seconds=600).window == timedelta(minutes=10)
    assert Grouping().window == timedelta(minutes=30)


def test_ingestion_defaults_match_the_documented_values() -> None:
    ingestion = Ingestion()

    assert ingestion.lookback_seconds == 3600
    assert ingestion.request_timeout_seconds == 30
    assert ingestion.max_retries == 3


def test_ingestion_lookback_is_offered_as_a_duration() -> None:
    assert Ingestion(lookback_seconds=900).lookback == timedelta(minutes=15)
    assert Ingestion().lookback == timedelta(hours=1)


def test_ingestion_bounds_are_independent_of_the_investigation_breakers() -> None:
    config: Config = InMemoryConfig(
        scope=Scope(owner="sre"),
        circuit_breakers=CircuitBreakers(
            mcp_call_timeout_seconds=90, max_mcp_retries=9
        ),
    )

    assert config.ingestion.request_timeout_seconds == 30
    assert config.ingestion.max_retries == 3


def test_changing_an_ingestion_bound_leaves_the_breakers_alone() -> None:
    config: Config = InMemoryConfig(
        scope=Scope(owner="sre"),
        ingestion=Ingestion(request_timeout_seconds=90, max_retries=9),
    )

    assert config.circuit_breakers.mcp_call_timeout_seconds == 30
    assert config.circuit_breakers.max_mcp_retries == 3


def test_critical_service_thresholds_have_documented_defaults() -> None:
    service = CriticalService()

    assert service.tier == CriticalService.DEFAULT_TIER
    assert service.latency_threshold_ms == 2000


def test_no_service_is_critical_unless_the_config_says_so() -> None:
    config: Config = InMemoryConfig(scope=Scope(owner="sre"))

    assert config.critical_services == {}
