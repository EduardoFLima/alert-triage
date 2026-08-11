"""A ``TriageLedger`` backed by SQLite, over the standard library's ``sqlite3``.

Everything storage-shaped stops here: the queries, the ISO-8601 text the
timestamps are kept as, and the driver's own exceptions. What leaves is
``Incident`` values, or a ``TriageLedgerError``. The tables those queries run
against are in ``schema``.

Instants are normalised to UTC on the way in and returned timezone-aware, so
no naive datetime ever escapes into cooldown arithmetic.
"""

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from alert_triage.adapters.sqlite_ledger.schema import SCHEMA
from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident
from alert_triage.domain.triage import is_closed
from alert_triage.ports.triage_ledger import TriageLedgerError


class SqliteTriageLedger:
    """The incidents on record, kept in a SQLite database.

    The connection is injected rather than opened here, exactly as the Datadog
    adapter takes an already-configured client: resolving where the database
    lives belongs to the composition root, and injecting it is what lets these
    tests run against ``:memory:`` with no filesystem.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        window: timedelta,
        cooldown: timedelta,
        retention: timedelta,
    ) -> None:
        """Bind the ledger to a connection, creating its schema if it is new.

        Args:
            connection: An open connection to the ledger's database.
            window: The grouping window, which bounds continuation and so is
                half of what decides an incident has closed.
            cooldown: How long a report suppresses the next one — the other
                half.
            retention: How long a closed incident is kept for a human to
                consult before it is deleted.

        Raises:
            TriageLedgerError: The schema could not be established, so nothing
                that follows could be believed.
        """
        self._connection = connection
        self._window = window
        self._cooldown = cooldown
        self._retention = retention
        with _translated("prepare the ledger's schema"):
            self._connection.executescript(SCHEMA)
            self._connection.commit()

    def open_incidents(self, service: str, now: datetime) -> Sequence[Incident]:
        """Retrieve the still-open incidents on record for a service.

        Incidents that have gone quiet are stamped closed as they are found,
        and are filtered out here rather than handed over for a caller to
        remember to skip. A record kept for a human to read is therefore
        unable to influence a decision.
        """
        with _translated(f"read the incidents on record for {service!r}"):
            rows = self._connection.execute(
                "SELECT id, service, last_reported_at, closed_at FROM incidents "
                "WHERE service = ? AND closed_at IS NULL ORDER BY id",
                (service,),
            ).fetchall()
            still_open = [
                incident
                for incident in (self._incident(row) for row in rows)
                if not self._close_if_quiet(incident, now)
            ]
            self._connection.commit()
            return still_open

    def record(self, incident: Incident, now: datetime) -> None:
        """Record an incident's state as of this run.

        History past its retention period is deleted in the same transaction:
        this is the only moment the ledger is already open and writing, so
        growth is bounded by the very event that causes it.
        """
        with _translated(f"record incident {incident.id!r}"):
            self._write(incident)
            self._forget_beyond_retention(now)
            self._connection.commit()

    def _close_if_quiet(self, incident: Incident, now: datetime) -> bool:
        """Stamp an incident closed if it has gone quiet, and say whether it had.

        Stamped rather than derived on each read: an incident closed at a
        moment, and retuning the cooldown afterwards must not move when that
        was and so age the record into deletion early.
        """
        if not is_closed(
            incident, now=now, window=self._window, cooldown=self._cooldown
        ):
            return False
        self._connection.execute(
            "UPDATE incidents SET closed_at = ? WHERE id = ?",
            (_as_text(now), incident.id),
        )
        return True

    def _forget_beyond_retention(self, now: datetime) -> None:
        """Delete the incidents that closed longer ago than history is kept."""
        cutoff = _as_text(now - self._retention)
        self._connection.execute(
            "DELETE FROM incident_alerts WHERE incident_id IN "
            "(SELECT id FROM incidents WHERE closed_at IS NOT NULL AND closed_at < ?)",
            (cutoff,),
        )
        self._connection.execute(
            "DELETE FROM incidents WHERE closed_at IS NOT NULL AND closed_at < ?",
            (cutoff,),
        )

    def _write(self, incident: Incident) -> None:
        """Write an incident and its alerts, replacing what was held before."""
        self._connection.execute(
            "INSERT INTO incidents (id, service, last_reported_at, closed_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "service = excluded.service, "
            "last_reported_at = excluded.last_reported_at, "
            "closed_at = excluded.closed_at",
            (
                incident.id,
                incident.service,
                _as_text(incident.last_reported_at),
                _as_text(incident.closed_at),
            ),
        )
        self._connection.execute(
            "DELETE FROM incident_alerts WHERE incident_id = ?", (incident.id,)
        )
        self._connection.executemany(
            "INSERT INTO incident_alerts "
            "(incident_id, source_id, service, fired_at, title, link) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    incident.id,
                    alert.source_id,
                    alert.service,
                    _as_text(alert.fired_at),
                    alert.title,
                    alert.link,
                )
                for alert in incident.alerts
            ],
        )

    def _incident(self, row: tuple[str, str, str | None, str | None]) -> Incident:
        """Rebuild one incident from its row and the alerts absorbed into it."""
        incident_id, service, last_reported_at, closed_at = row
        return Incident(
            id=incident_id,
            service=service,
            alerts=self._alerts(incident_id),
            last_reported_at=_as_instant(last_reported_at),
            closed_at=_as_instant(closed_at),
        )

    def _alerts(self, incident_id: str) -> tuple[Alert, ...]:
        """Read the alerts absorbed into one incident, oldest first."""
        rows = self._connection.execute(
            "SELECT source_id, service, fired_at, title, link FROM incident_alerts "
            "WHERE incident_id = ? ORDER BY fired_at",
            (incident_id,),
        ).fetchall()
        return tuple(
            Alert(
                service=service,
                fired_at=_as_utc(fired_at),
                source_id=source_id,
                title=title,
                link=link,
            )
            for source_id, service, fired_at, title, link in rows
        )


@contextmanager
def _translated(attempt: str) -> Iterator[None]:
    """Turn the driver's failures into the port's own, at the boundary.

    Past here a caller catches ``TriageLedgerError`` and never learns SQLite
    was involved — and, more to the point, never mistakes a failed read for a
    quiet period.
    """
    try:
        yield
    except sqlite3.Error as error:
        raise TriageLedgerError(
            f"Could not {attempt} in the triage ledger: {error}"
        ) from error


def _as_text(instant: datetime | None) -> str | None:
    """Store an instant as ISO-8601 UTC text, since SQLite has no datetime type."""
    if instant is None:
        return None
    return _to_utc(instant).isoformat()


def _as_instant(text: str | None) -> datetime | None:
    """Read back an instant that the schema allows to be absent."""
    return None if text is None else _as_utc(text)


def _as_utc(text: str) -> datetime:
    """Read back a stored instant, timezone-aware, in UTC."""
    return _to_utc(datetime.fromisoformat(text))


def _to_utc(instant: datetime) -> datetime:
    """Express an instant in UTC, so instants from any source compare alike."""
    if instant.tzinfo is None:
        return instant.replace(tzinfo=UTC)
    return instant.astimezone(UTC)
