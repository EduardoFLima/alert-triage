from typing import Protocol, runtime_checkable

from alert_triage.configuration.settings import (
    CircuitBreakers,
    Grouping,
    Ingestion,
    Investigation,
    Ledger,
    ReNotify,
    Scope,
)


class ConfigError(Exception):
    """Configuration could not be resolved, so the application must not start."""


@runtime_checkable
class Config(Protocol):
    @property
    def scope(self) -> Scope: ...

    @property
    def grouping(self) -> Grouping: ...

    @property
    def ingestion(self) -> Ingestion: ...

    @property
    def re_notify(self) -> ReNotify: ...

    @property
    def ledger(self) -> Ledger: ...

    @property
    def investigation(self) -> Investigation: ...

    @property
    def circuit_breakers(self) -> CircuitBreakers: ...
