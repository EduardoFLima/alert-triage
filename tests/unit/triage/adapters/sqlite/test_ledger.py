import sqlite3
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone

import pytest

from alert_triage.triage.adapters.sqlite import SqliteTriageLedger
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.grouping import AlertGroup
from alert_triage.triage.domain.incident import Incident
from alert_triage.triage.domain.policy import triage
from alert_triage.triage.ports.ledger import TriageLedgerError

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=30)
COOLDOWN = timedelta(days=2)
RETENTION = timedelta(days=30)


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    """An in-process database: no filesystem, so this stays a unit test."""
    open_connection = sqlite3.connect(":memory:")
    yield open_connection
    open_connection.close()


def _ledger(
    connection: sqlite3.Connection,
    cooldown: timedelta = COOLDOWN,
    retention: timedelta = RETENTION,
) -> SqliteTriageLedger:
    return SqliteTriageLedger(
        connection, window=WINDOW, cooldown=cooldown, retention=retention
    )


def _alert(source_id: str, offset: timedelta = timedelta()) -> Alert:
    return Alert(
        service="checkout",
        fired_at=NOON + offset,
        source_id=source_id,
        title=f"Latency above threshold ({source_id})",
        link=f"https://app.datadoghq.com/event/event?id={source_id}",
    )


def _incident(*alerts: Alert, incident_id: str = "incident-1") -> Incident:
    return Incident(
        id=incident_id,
        service="checkout",
        alerts=alerts or (_alert("a"),),
        last_reported_at=NOON,
    )


def test_a_recorded_incident_is_read_back_as_it_was_recorded(
    connection: sqlite3.Connection,
) -> None:
    ledger = _ledger(connection)
    incident = _incident(_alert("a"), _alert("b", timedelta(minutes=5)))

    ledger.record(incident, NOON)

    assert ledger.open_incidents("checkout", NOON) == [incident]


def test_the_alerts_keep_their_identity_and_provenance(
    connection: sqlite3.Connection,
) -> None:
    """A report naming an incident without naming its alerts is not actionable."""
    ledger = _ledger(connection)
    alert = _alert("a")
    ledger.record(_incident(alert), NOON)

    (recovered,) = ledger.open_incidents("checkout", NOON)[0].alerts

    assert recovered.source_id == alert.source_id
    assert recovered.fired_at == alert.fired_at
    assert recovered.service == alert.service
    assert recovered.title == alert.title
    assert recovered.link == alert.link


def test_a_service_with_nothing_on_record_reads_back_empty(
    connection: sqlite3.Connection,
) -> None:
    """A first run against fresh storage is not an error."""
    ledger = _ledger(connection)

    assert ledger.open_incidents("checkout", NOON) == []


def test_only_the_service_asked_about_is_read_back(
    connection: sqlite3.Connection,
) -> None:
    ledger = _ledger(connection)
    ledger.record(_incident(), NOON)

    assert ledger.open_incidents("payments", NOON) == []


def test_recording_an_incident_again_replaces_what_was_held(
    connection: sqlite3.Connection,
) -> None:
    ledger = _ledger(connection)
    incident = _incident(_alert("a"))
    ledger.record(incident, NOON)

    grown = incident.absorb([_alert("b", timedelta(minutes=5))])
    ledger.record(grown, NOON)

    assert ledger.open_incidents("checkout", NOON) == [grown]


def test_timestamps_come_back_timezone_aware_in_utc(
    connection: sqlite3.Connection,
) -> None:
    """A naive datetime escaping here would blow up inside cooldown arithmetic."""
    elsewhere = timezone(timedelta(hours=2))
    fired_at = datetime(2026, 8, 7, 14, 0, tzinfo=elsewhere)
    incident = Incident(
        id="incident-1",
        service="checkout",
        alerts=(Alert(service="checkout", fired_at=fired_at, source_id="a"),),
        last_reported_at=datetime(2026, 8, 7, 14, 30, tzinfo=elsewhere),
    )
    ledger = _ledger(connection)

    ledger.record(incident, NOON)

    (recovered,) = ledger.open_incidents("checkout", NOON)
    assert recovered.alerts[0].fired_at == fired_at == NOON
    assert recovered.alerts[0].fired_at.utcoffset() == timedelta(0)
    assert recovered.last_reported_at is not None
    assert recovered.last_reported_at.utcoffset() == timedelta(0)


def _rows(connection: sqlite3.Connection, statement: str) -> list[tuple[object, ...]]:
    return connection.execute(statement).fetchall()


def _long_after_closing() -> datetime:
    return NOON + COOLDOWN + WINDOW + timedelta(minutes=1)


def test_an_incident_that_has_gone_quiet_is_no_longer_offered(
    connection: sqlite3.Connection,
) -> None:
    ledger = _ledger(connection)
    ledger.record(_incident(), NOON)

    assert ledger.open_incidents("checkout", _long_after_closing()) == []


def test_only_the_open_incident_is_offered_beside_retained_history(
    connection: sqlite3.Connection,
) -> None:
    ledger = _ledger(connection)
    quiet = _incident(_alert("a"), incident_id="closed-one")
    ledger.record(quiet, NOON)
    ledger.open_incidents("checkout", _long_after_closing())

    still_firing = Incident(
        id="open-one",
        service="checkout",
        alerts=(_alert("b", COOLDOWN + WINDOW),),
        last_reported_at=NOON + COOLDOWN + WINDOW,
    )
    ledger.record(still_firing, _long_after_closing())

    on_record = ledger.open_incidents("checkout", _long_after_closing())
    assert [incident.id for incident in on_record] == ["open-one"]


def test_the_instant_an_incident_closed_is_stamped_once(
    connection: sqlite3.Connection,
) -> None:
    """Retuning the cooldown must not move a closure that already happened."""
    closed_at = _long_after_closing()
    _ledger(connection).record(_incident(), NOON)
    _ledger(connection).open_incidents("checkout", closed_at)

    retuned = _ledger(connection, cooldown=timedelta(days=90))
    retuned.open_incidents("checkout", closed_at + timedelta(days=7))

    assert _rows(connection, "SELECT closed_at FROM incidents") == [
        (closed_at.isoformat(),)
    ]


def test_a_recently_closed_incident_is_kept_with_what_it_recorded(
    connection: sqlite3.Connection,
) -> None:
    ledger = _ledger(connection)
    ledger.record(_incident(_alert("a"), _alert("b", timedelta(minutes=5))), NOON)
    closed_at = _long_after_closing()
    ledger.open_incidents("checkout", closed_at)

    ledger.record(_incident(incident_id="another"), closed_at + RETENTION)

    assert _rows(
        connection, "SELECT last_reported_at FROM incidents WHERE id = 'incident-1'"
    ) == [(NOON.isoformat(),)]
    kept_alerts = _rows(
        connection,
        "SELECT source_id FROM incident_alerts WHERE incident_id = 'incident-1'",
    )
    assert len(kept_alerts) == 2


def test_an_incident_closed_longer_ago_than_retention_is_deleted(
    connection: sqlite3.Connection,
) -> None:
    ledger = _ledger(connection)
    ledger.record(_incident(), NOON)
    closed_at = _long_after_closing()
    ledger.open_incidents("checkout", closed_at)

    ledger.record(
        _incident(incident_id="another"), closed_at + RETENTION + timedelta(seconds=1)
    )

    assert _rows(connection, "SELECT id FROM incidents") == [("another",)]
    assert (
        _rows(
            connection,
            "SELECT incident_id FROM incident_alerts WHERE incident_id = 'incident-1'",
        )
        == []
    )


def test_a_read_that_fails_is_not_reported_as_an_empty_ledger(
    connection: sqlite3.Connection,
) -> None:
    """An empty result would look exactly like 'nothing reported yet'."""
    ledger = _ledger(connection)
    connection.close()

    with pytest.raises(TriageLedgerError, match="checkout"):
        ledger.open_incidents("checkout", NOON)


def test_a_write_that_fails_does_not_complete_silently(
    connection: sqlite3.Connection,
) -> None:
    ledger = _ledger(connection)
    connection.close()

    with pytest.raises(TriageLedgerError, match="incident-1"):
        ledger.record(_incident(), NOON)


def test_retained_history_decides_as_though_the_record_were_deleted(
    connection: sqlite3.Connection,
) -> None:
    """The arriving run re-delivers an alert the retained incident absorbed."""
    at = _long_after_closing()
    retaining = _ledger(connection)
    retaining.record(_incident(), NOON)
    retaining.open_incidents("checkout", at)

    forgotten = sqlite3.connect(":memory:")
    arriving = AlertGroup(
        service="checkout", alerts=(_alert("a"), _alert("b", COOLDOWN + WINDOW))
    )
    decisions = [
        triage(
            arriving,
            ledger.open_incidents("checkout", at),
            now=at,
            window=WINDOW,
            cooldown=COOLDOWN,
            max_attempts=3,
            new_id=lambda: "incident-2",
        )
        for ledger in (retaining, _ledger(forgotten))
    ]
    forgotten.close()

    assert decisions[0] == decisions[1]
    assert decisions[0].should_report


def test_a_naive_timestamp_is_read_back_as_an_instant_in_utc(
    connection: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A source that lost its offset must not leak a naive datetime through.

    Pinned away from UTC on purpose: a naive value read as the machine's own
    local time would shift the instant, and every cooldown measured from it.
    """
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()

    incident = Incident(
        id="incident-1",
        service="checkout",
        alerts=(Alert(service="checkout", fired_at=datetime(2026, 8, 7, 12, 0)),),
        last_reported_at=datetime(2026, 8, 7, 12, 0),
    )
    ledger = _ledger(connection)

    ledger.record(incident, NOON)

    (recovered,) = ledger.open_incidents("checkout", NOON)
    assert recovered.alerts[0].fired_at == NOON
    assert recovered.last_reported_at == NOON
