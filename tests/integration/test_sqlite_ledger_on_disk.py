import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alert_triage.adapters.sqlite_ledger import SqliteTriageLedger
from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=30)
COOLDOWN = timedelta(days=2)
RETENTION = timedelta(days=30)


def _ledger(connection: sqlite3.Connection) -> SqliteTriageLedger:
    return SqliteTriageLedger(
        connection, window=WINDOW, cooldown=COOLDOWN, retention=RETENTION
    )


def _incident() -> Incident:
    return Incident(
        id="incident-1",
        service="checkout",
        alerts=(
            Alert(
                service="checkout",
                fired_at=NOON,
                source_id="a",
                title="Latency above threshold",
                link="https://app.datadoghq.com/event/event?id=a",
            ),
        ),
        last_reported_at=NOON,
    )


def test_an_incident_recorded_to_a_file_survives_the_process_that_wrote_it(
    tmp_path: Path,
) -> None:
    """What makes dedup work across runs: a second process reads the first's record."""
    location = tmp_path / "ledger.db"

    writing = sqlite3.connect(location)
    _ledger(writing).record(_incident(), NOON)
    writing.close()

    reading = sqlite3.connect(location)
    on_record = _ledger(reading).open_incidents("checkout", NOON + timedelta(minutes=1))
    reading.close()

    assert on_record == [_incident()]


def test_a_fresh_deployment_needs_no_migration_step(tmp_path: Path) -> None:
    location = tmp_path / "absent.db"

    connection = sqlite3.connect(location)
    on_record = _ledger(connection).open_incidents("checkout", NOON)
    connection.close()

    assert on_record == []
    assert location.is_file()
