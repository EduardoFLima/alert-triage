"""The port through which the application reads its configuration."""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from alert_triage.domain.config import CircuitBreakers, GroupingSettings, Scope


class ConfigurationError(Exception):
    """A configuration value the application cannot start without is missing."""


@runtime_checkable
class Config(Protocol):
    """Fully resolved configuration, from whatever source supplied it.

    Every value is resolved before the port is handed out, so a consumer
    never has to know that a value could have come from a file, the
    environment, or a default — nor handle a resolution failure mid-run.
    """

    @property
    def scope(self) -> Scope:
        """The team whose alerts this run triages."""
        ...

    @property
    def circuit_breakers(self) -> CircuitBreakers:
        """Thresholds bounding an investigation."""
        ...

    @property
    def grouping(self) -> GroupingSettings:
        """How alerts are combined into incidents."""
        ...

    @property
    def critical_services(self) -> Mapping[str, Mapping[str, object]]:
        """Per-service overrides, keyed by service tag.

        Purely what an operator supplied: a service absent from the mapping,
        or a key absent from a service's entry, means no override exists.
        Nothing here is filled in with a default.
        """
        ...
