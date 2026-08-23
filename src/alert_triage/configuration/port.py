"""The Config port: everything a deployment is configured with, already resolved.

A consumer asks for settings through this and learns nothing about where they
came from — which is what lets a test hand one a plain object and lets a
deployment choose its own source.
"""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from alert_triage.configuration.settings import (
    CircuitBreakers,
    CriticalService,
    Grouping,
    Ingestion,
    Investigation,
    Ledger,
    ReNotify,
    Scope,
)


class ConfigError(Exception):
    """Configuration could not be resolved, so the application must not start.

    Defined beside the port rather than in the implementation that raises it:
    a caller decides what to do about unusable configuration without knowing
    which source produced it.
    """


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
    def ingestion(self) -> Ingestion:
        """Settings alert fetching is driven by."""

    @property
    def re_notify(self) -> ReNotify:
        """How long a report suppresses the next one."""

    @property
    def ledger(self) -> Ledger:
        """How much triage history is kept once an incident has closed."""

    @property
    def investigation(self) -> Investigation:
        """How an investigation reasons, and how often it is attempted."""

    @property
    def circuit_breakers(self) -> CircuitBreakers:
        """Bounds an investigation runs under."""

    @property
    def critical_services(self) -> Mapping[str, CriticalService]:
        """Services declared critical, keyed by service tag. Empty means none."""
