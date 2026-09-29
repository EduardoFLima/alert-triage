from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import ClassVar


@dataclass(frozen=True)
class ServiceScope:
    """Being listed means in scope; critical only raises urgency."""

    critical: bool = False


NOT_DECLARED = ServiceScope()


@dataclass(frozen=True)
class Scope:
    """The environment narrows owner/services; it never stands in for them."""

    DEFAULT_ENV: ClassVar[str] = "prod"

    owner: str | None = None
    services: Mapping[str, ServiceScope] = field(default_factory=dict)
    env: str = DEFAULT_ENV

    def for_service(self, service: str) -> ServiceScope:
        """Missing services are ordinary in owner-bounded runs, not errors."""
        return self.services.get(service, NOT_DECLARED)


@dataclass(frozen=True)
class Grouping:
    DEFAULT_WINDOW_SECONDS: ClassVar[int] = 1800

    window_seconds: int = DEFAULT_WINDOW_SECONDS

    @property
    def window(self) -> timedelta:
        return timedelta(seconds=self.window_seconds)


@dataclass(frozen=True)
class Ingestion:
    """Request bounds are separate from investigation circuit breakers."""

    DEFAULT_LOOKBACK_SECONDS: ClassVar[int] = 3600

    lookback_seconds: int = DEFAULT_LOOKBACK_SECONDS
    request_timeout_seconds: int = 30
    max_retries: int = 3

    @property
    def lookback(self) -> timedelta:
        return timedelta(seconds=self.lookback_seconds)


@dataclass(frozen=True)
class ReNotify:
    DEFAULT_COOLDOWN_SECONDS: ClassVar[int] = 172_800

    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS

    @property
    def cooldown(self) -> timedelta:
        return timedelta(seconds=self.cooldown_seconds)


@dataclass(frozen=True)
class Ledger:
    """Storage location is deployment data; this governs retention only."""

    DEFAULT_RETENTION_SECONDS: ClassVar[int] = 2_592_000

    retention_seconds: int = DEFAULT_RETENTION_SECONDS

    @property
    def retention(self) -> timedelta:
        return timedelta(seconds=self.retention_seconds)


@dataclass(frozen=True)
class SpecialistModel:
    model: str


@dataclass(frozen=True)
class Investigation:
    """Model choice is behavior; credentials stay in deployment settings."""

    DEFAULT_MODEL: ClassVar[str] = "gemini-2.5-flash"
    DEFAULT_MAX_ATTEMPTS: ClassVar[int] = 3

    model: str = DEFAULT_MODEL
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    specialists: Mapping[str, SpecialistModel] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must allow at least one investigation")


@dataclass(frozen=True)
class CircuitBreakers:
    """Each breaker is read by the code it names; stale keys must fail loudly."""

    DEFAULT_MAX_TOOL_CALLS_PER_AGENT: ClassVar[int] = 12
    DEFAULT_MAX_AGENT_HOPS: ClassVar[int] = 8
    DEFAULT_MAX_INVESTIGATION_DURATION_SECONDS: ClassVar[int] = 300
    DEFAULT_MCP_CALL_TIMEOUT_SECONDS: ClassVar[int] = 30

    max_tool_calls_per_agent: int = DEFAULT_MAX_TOOL_CALLS_PER_AGENT
    max_agent_hops: int = DEFAULT_MAX_AGENT_HOPS
    max_investigation_duration_seconds: int = DEFAULT_MAX_INVESTIGATION_DURATION_SECONDS
    mcp_call_timeout_seconds: int = DEFAULT_MCP_CALL_TIMEOUT_SECONDS
