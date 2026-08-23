"""SQLite adapter for the ``TriageLedger`` port.

Durable across runs, transactional, and one file to move or delete — which is
what makes dedup work for a manual v1 deployment without adding a dependency.
"""

from alert_triage.triage.adapters.sqlite.ledger import SqliteTriageLedger
from alert_triage.triage.adapters.sqlite.location import (
    DEFAULT_LEDGER_PATH,
    LEDGER_PATH_VARIABLE,
    resolve_ledger_path,
)

__all__ = [
    "DEFAULT_LEDGER_PATH",
    "LEDGER_PATH_VARIABLE",
    "SqliteTriageLedger",
    "resolve_ledger_path",
]
