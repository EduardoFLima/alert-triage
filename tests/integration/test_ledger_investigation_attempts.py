import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alert_triage.triage.adapters.sqlite.ledger import SqliteTriageLedger
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.incident import Incident

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=30)
COOLDOWN = timedelta(days=2)
RETENTION = timedelta(days=30)

BEFORE_ATTEMPTS_WERE_TRACKED = """
CREATE TABLE incidents (
    id               TEXT PRIMARY KEY,
    service          TEXT NOT NULL,
    last_reported_at TEXT,
    closed_at        TEXT
);
CREATE TABLE incident_alerts (
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    source_id   TEXT NOT NULL,
    service     TEXT NOT NULL,
    fired_at    TEXT NOT NULL,
    title       TEXT NOT NULL,
    link        TEXT NOT NULL
);
INSERT INTO incidents (id, service, last_reported_at, closed_at)
VALUES ('incident-old', 'checkout', NULL, NULL);
INSERT INTO incident_alerts
(incident_id, source_id, service, fired_at, title, link)
VALUES ('incident-old', 'a', 'checkout', '2026-08-15T12:00:00+00:00', '', '');
"""


def _ledger(connection: sqlite3.Connection) -> SqliteTriageLedger:
    return SqliteTriageLedger(
        connection, window=WINDOW, cooldown=COOLDOWN, retention=RETENTION
    )


def _incident(attempts: int) -> Incident:
    return Incident(
        id="incident-1",
        service="checkout",
        alerts=(Alert(service="checkout", fired_at=NOON, source_id="a"),),
        investigation_attempts=attempts,
    )


def test_spent_attempts_survive_a_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"

    with closing(sqlite3.connect(path)) as writing:
        _ledger(writing).record(_incident(attempts=2), NOON)

    with closing(sqlite3.connect(path)) as reading:
        (recovered,) = _ledger(reading).open_incidents("checkout", NOON)

    assert recovered.investigation_attempts == 2


def test_an_incident_with_no_attempts_spent_reads_back_as_none_spent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"

    with closing(sqlite3.connect(path)) as writing:
        _ledger(writing).record(_incident(attempts=0), NOON)

    with closing(sqlite3.connect(path)) as reading:
        (recovered,) = _ledger(reading).open_incidents("checkout", NOON)

    assert recovered.investigation_attempts == 0


def test_a_ledger_written_before_attempts_were_tracked_still_opens(
    tmp_path: Path,
) -> None:
    """No backfill and no migration step: an existing file opens and works."""
    path = tmp_path / "ledger.db"
    with closing(sqlite3.connect(path)) as seeding:
        seeding.executescript(BEFORE_ATTEMPTS_WERE_TRACKED)
        seeding.commit()

    with closing(sqlite3.connect(path)) as reading:
        (recovered,) = _ledger(reading).open_incidents("checkout", NOON)

    assert recovered.id == "incident-old"
    assert recovered.investigation_attempts == 0


def test_the_attempts_recorded_are_the_ones_a_later_run_retries_from(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"

    with closing(sqlite3.connect(path)) as first_run:
        ledger = _ledger(first_run)
        ledger.record(_incident(attempts=0).investigation_failed(), NOON)

    with closing(sqlite3.connect(path)) as second_run:
        ledger = _ledger(second_run)
        (carried,) = ledger.open_incidents("checkout", NOON)
        ledger.record(carried.investigation_failed(), NOON)

    with closing(sqlite3.connect(path)) as third_run:
        (recovered,) = _ledger(third_run).open_incidents("checkout", NOON)

    assert recovered.investigation_attempts == 2
