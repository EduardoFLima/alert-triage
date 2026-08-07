"""The Config port: resolved settings, with no notion of where they came from.

A consumer depends on these values, never on YAML files or environment
variables — which is what lets a test hand one a plain object and lets a
deployment choose its own source. The default values here are the documented
defaults from ``docs/vision.md``; an implementation resolves what an operator
supplied on top of them.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar, Protocol, runtime_checkable


class ConfigError(Exception):
    """Configuration could not be resolved, so the application must not start.

    Defined beside the port rather than in the implementation that raises it:
    a caller decides what to do about unusable configuration without knowing
    which source produced it.
    """


@dataclass(frozen=True)
class Scope:
    """What the job watches. Mandatory: there is no "watch everything" default.

    Attributes:
        datadog_team: The single Datadog team whose alerts are in scope.
    """

    datadog_team: str


@dataclass(frozen=True)
class Grouping:
    """How far apart alerts of one service may fire and still be one incident.

    Attributes:
        window_seconds: The grouping time window, in seconds.
    """

    DEFAULT_WINDOW_SECONDS: ClassVar[int] = 300

    window_seconds: int = DEFAULT_WINDOW_SECONDS

    @property
    def window(self) -> timedelta:
        """The window as a duration, which is what the grouping logic takes."""
        return timedelta(seconds=self.window_seconds)


@dataclass(frozen=True)
class CircuitBreakers:
    """Bounds on a multi-agent investigation, one per way it can run away.

    Attributes:
        max_tool_calls_per_agent: Tool calls one agent may make.
        max_agent_hops: Handoffs between agents in one investigation.
        max_investigation_duration_seconds: Wall-clock bound per investigation.
        max_mcp_retries: Retries of a failed MCP call.
        mcp_call_timeout_seconds: Timeout of a single MCP call.
    """

    max_tool_calls_per_agent: int = 8
    max_agent_hops: int = 2
    max_investigation_duration_seconds: int = 120
    max_mcp_retries: int = 3
    mcp_call_timeout_seconds: int = 30


@dataclass(frozen=True)
class CriticalService:
    """Escalation overrides for a service an operator declared critical.

    Being listed is what makes a service critical; every threshold within the
    entry is optional and falls back to the default beside it.

    Attributes:
        tier: Criticality tier this service is escalated under.
        latency_threshold_ms: Latency above which escalation bypasses batching.
    """

    DEFAULT_TIER: ClassVar[str] = "critical"
    DEFAULT_LATENCY_THRESHOLD_MS: ClassVar[int] = 1000

    tier: str = DEFAULT_TIER
    latency_threshold_ms: int = DEFAULT_LATENCY_THRESHOLD_MS


@runtime_checkable
class Config(Protocol):
    """Configuration as the rest of the application sees it: already resolved."""

    @property
    def scope(self) -> Scope:
        """What the job watches."""

    @property
    def grouping(self) -> Grouping:
        """Settings the grouping logic is driven by."""

    @property
    def circuit_breakers(self) -> CircuitBreakers:
        """Bounds an investigation runs under."""

    @property
    def critical_services(self) -> Mapping[str, CriticalService]:
        """Services declared critical, keyed by service tag. Empty means none."""
