"""The configuration values the domain reasons in terms of.

These are the resolved shapes, not the file format: whether a value came
from ``config.yaml``, an environment variable, or a built-in default is the
adapter's concern and invisible here.
"""

from dataclasses import dataclass
from datetime import timedelta

DEFAULT_GROUPING_WINDOW_SECONDS = 300


@dataclass(frozen=True, slots=True)
class Scope:
    """What the job watches. Mandatory — there is no "everything" fallback.

    Attributes:
        datadog_team: The single Datadog team whose alerts are triaged.
            Widening scope beyond one team is a post-v1 extension.
    """

    datadog_team: str


@dataclass(frozen=True, slots=True)
class CircuitBreakers:
    """Bounds on a multi-agent investigation that could otherwise run away.

    The defaults are the ones documented in ``docs/vision.md``; a deployment
    overrides individual thresholds without restating the rest.
    """

    max_tool_calls_per_agent: int = 8
    max_agent_hops: int = 2
    max_investigation_duration_seconds: int = 120
    max_mcp_retries: int = 3
    mcp_call_timeout_seconds: int = 30


@dataclass(frozen=True, slots=True)
class GroupingSettings:
    """How far apart alerts of one service may fire and still be one incident.

    Tunable per environment because the right window follows a team's alert
    volume, which no single built-in number gets right everywhere.
    """

    window_seconds: int = DEFAULT_GROUPING_WINDOW_SECONDS

    @property
    def window(self) -> timedelta:
        """The grouping window as a duration, ready for ``group_alerts``."""
        return timedelta(seconds=self.window_seconds)
