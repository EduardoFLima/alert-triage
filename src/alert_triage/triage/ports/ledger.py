"""The ledger remembers incidents without deciding what they mean."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from alert_triage.triage.domain.incident import Incident


class TriageLedgerError(Exception):
    """A failed read must not be mistaken for no incidents on record."""


@runtime_checkable
class TriageLedger(Protocol):
    def open_incidents(self, service: str, now: datetime) -> Sequence[Incident]:
        """Return open incidents only; retained history cannot influence decisions."""
        ...

    def record(self, incident: Incident, now: datetime) -> None: ...
