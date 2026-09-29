import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from alert_triage.triage.adapters.sqlite.schema import ADDED_COLUMNS, SCHEMA
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.incident import Incident
from alert_triage.triage.domain.policy import is_closed
from alert_triage.triage.ports.ledger import TriageLedgerError


class SqliteTriageLedger:
    """The connection is injected so tests can use ``:memory:``."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        window: timedelta,
        cooldown: timedelta,
        retention: timedelta,
    ) -> None:
        self._connection = connection
        self._window = window
        self._cooldown = cooldown
        self._retention = retention
        with _translated("prepare the ledger's schema"):
            self._connection.executescript(SCHEMA)
            self._add_missing_columns()
            self._connection.commit()

    def _add_missing_columns(self) -> None:
        for statement in ADDED_COLUMNS:
            try:
                self._connection.execute(statement)
            except sqlite3.OperationalError as error:
                if "duplicate column name" not in str(error):
                    raise

    def open_incidents(self, service: str, now: datetime) -> Sequence[Incident]:
        with _translated(f"read the incidents on record for {service!r}"):
            rows = self._connection.execute(
                "SELECT id, service, last_reported_at, closed_at, "
                "investigation_attempts FROM incidents "
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
        with _translated(f"record incident {incident.id!r}"):
            self._write(incident)
            self._forget_beyond_retention(now)
            self._connection.commit()

    def _close_if_quiet(self, incident: Incident, now: datetime) -> bool:
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
        self._connection.execute(
            "INSERT INTO incidents "
            "(id, service, last_reported_at, closed_at, investigation_attempts) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "service = excluded.service, "
            "last_reported_at = excluded.last_reported_at, "
            "closed_at = excluded.closed_at, "
            "investigation_attempts = excluded.investigation_attempts",
            (
                incident.id,
                incident.service,
                _as_text(incident.last_reported_at),
                _as_text(incident.closed_at),
                incident.investigation_attempts,
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

    def _incident(self, row: tuple[str, str, str | None, str | None, int]) -> Incident:
        incident_id, service, last_reported_at, closed_at, attempts = row
        return Incident(
            id=incident_id,
            service=service,
            alerts=self._alerts(incident_id),
            last_reported_at=_as_instant(last_reported_at),
            closed_at=_as_instant(closed_at),
            investigation_attempts=attempts,
        )

    def _alerts(self, incident_id: str) -> tuple[Alert, ...]:
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
    """Keep SQLite failures from reading as a quiet period."""
    try:
        yield
    except sqlite3.Error as error:
        raise TriageLedgerError(
            f"Could not {attempt} in the triage ledger: {error}"
        ) from error


def _as_text(instant: datetime | None) -> str | None:
    if instant is None:
        return None
    return _to_utc(instant).isoformat()


def _as_instant(text: str | None) -> datetime | None:
    return None if text is None else _as_utc(text)


def _as_utc(text: str) -> datetime:
    return _to_utc(datetime.fromisoformat(text))


def _to_utc(instant: datetime) -> datetime:
    if instant.tzinfo is None:
        return instant.replace(tzinfo=UTC)
    return instant.astimezone(UTC)
