from dataclasses import dataclass, field
from datetime import timedelta

import pytest

from alert_triage.configuration.port import Config
from alert_triage.configuration.settings import (
    CircuitBreakers,
    Grouping,
    Ingestion,
    Investigation,
    Ledger,
    ReNotify,
    Scope,
    ScopedService,
)


@dataclass(frozen=True)
class InMemoryConfig:
    """What a test double for the port looks like: values, no source."""

    scope: Scope
    grouping: Grouping = field(default_factory=Grouping)
    ingestion: Ingestion = field(default_factory=Ingestion)
    circuit_breakers: CircuitBreakers = field(default_factory=CircuitBreakers)
    re_notify: ReNotify = field(default_factory=ReNotify)
    ledger: Ledger = field(default_factory=Ledger)
    investigation: Investigation = field(default_factory=Investigation)


def _config(**overrides: object) -> InMemoryConfig:
    return InMemoryConfig(scope=Scope(owner="sre"), **overrides)  # type: ignore[arg-type]


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


def test_a_watched_service_is_ordinary_until_an_operator_says_otherwise() -> None:
    service = ScopedService(name="checkout")

    assert service.name == "checkout"
    assert service.acceptable_latency_ms is None
    assert service.critical is False


def test_a_scope_watches_every_service_its_owner_owns_by_default() -> None:
    assert Scope(owner="sre").services == ()


def test_the_services_alone_are_a_scope() -> None:
    """An owner and a list of services narrow along different axes."""
    scope = Scope(services=(ScopedService(name="checkout"),))

    assert scope.owner is None
    assert [service.name for service in scope.services] == ["checkout"]


def test_an_owner_and_its_services_are_a_scope_together() -> None:
    scope = Scope(owner="sre", services=(ScopedService(name="checkout"),))

    assert scope.owner == "sre"
    assert [service.name for service in scope.services] == ["checkout"]


def test_a_scope_naming_neither_watches_nothing_and_is_refused() -> None:
    """The fallback that does not exist is "watch everything"."""
    with pytest.raises(ValueError, match="owner"):
        Scope()


def test_the_re_notify_cooldown_defaults_to_the_documented_two_days() -> None:
    assert ReNotify().cooldown_seconds == ReNotify.DEFAULT_COOLDOWN_SECONDS
    assert ReNotify().cooldown == timedelta(days=2)


def test_the_cooldown_is_offered_to_the_domain_as_a_duration() -> None:
    assert ReNotify(cooldown_seconds=3600).cooldown == timedelta(hours=1)


def test_the_ledger_retains_closed_incidents_for_a_documented_thirty_days() -> None:
    assert Ledger().retention_seconds == Ledger.DEFAULT_RETENTION_SECONDS
    assert Ledger().retention == timedelta(days=30)


def test_retention_is_offered_as_a_duration() -> None:
    assert Ledger(retention_seconds=86400).retention == timedelta(days=1)


def test_retuning_the_cooldown_leaves_how_long_history_is_kept_alone() -> None:
    config: Config = InMemoryConfig(
        scope=Scope(owner="sre"), re_notify=ReNotify(cooldown_seconds=60)
    )

    assert config.ledger.retention == timedelta(days=30)


def test_retuning_retention_leaves_how_often_a_report_repeats_alone() -> None:
    config: Config = InMemoryConfig(
        scope=Scope(owner="sre"), ledger=Ledger(retention_seconds=60)
    )

    assert config.re_notify.cooldown == timedelta(days=2)


def test_the_investigation_model_has_a_documented_default() -> None:
    assert Investigation().model == Investigation.DEFAULT_MODEL


def test_an_investigation_gets_three_attempts_by_default() -> None:
    assert Investigation().max_attempts == Investigation.DEFAULT_MAX_ATTEMPTS
    assert Investigation.DEFAULT_MAX_ATTEMPTS == 3


def test_the_operator_can_choose_the_model_and_the_attempts() -> None:
    investigation = Investigation(model="some-other-model", max_attempts=1)

    assert investigation.model == "some-other-model"
    assert investigation.max_attempts == 1


def test_an_attempt_bound_below_one_is_refused() -> None:
    """Zero attempts would leave every incident permanently uninvestigable."""
    with pytest.raises(ValueError, match="max_attempts"):
        Investigation(max_attempts=0)


def test_a_config_carries_its_investigation_settings() -> None:
    config = _config(investigation=Investigation(max_attempts=2))

    assert config.investigation.max_attempts == 2


def test_a_config_defaults_its_investigation_settings() -> None:
    assert _config().investigation.max_attempts == 3
