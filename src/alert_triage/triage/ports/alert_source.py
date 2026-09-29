"""Alert sources translate platform payloads into domain alerts."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from alert_triage.triage.domain.alert import Alert


class AlertSourceError(Exception):
    """A failed fetch must not be mistaken for a quiet period."""


@runtime_checkable
class AlertSource(Protocol):
    def fetch_since(self, since: datetime) -> Sequence[Alert]:
        """Return every page; an empty result means nothing fired."""
        ...
