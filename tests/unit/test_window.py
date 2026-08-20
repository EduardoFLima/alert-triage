from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident
from alert_triage.domain.window import Window

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def _alert(offset: timedelta = timedelta()) -> Alert:
    return Alert(service="checkout", fired_at=NOON + offset)


def _incident(*alerts: Alert) -> Incident:
    return Incident(id="incident-1", service="checkout", alerts=alerts)


def test_a_window_carries_the_instants_it_spans() -> None:
    window = Window(start=NOON, end=NOON + timedelta(minutes=7))

    assert window.start == NOON
    assert window.end == NOON + timedelta(minutes=7)


def test_a_window_may_span_a_single_instant() -> None:
    """One alert is a real incident, and it spans no time at all."""
    assert Window(start=NOON, end=NOON).start == NOON


def test_a_window_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValueError, match="end"):
        Window(start=NOON, end=NOON - timedelta(seconds=1))


def test_an_incidents_window_spans_its_earliest_to_its_latest_alert() -> None:
    first = _alert()
    last = _alert(timedelta(minutes=7))

    window = _incident(last, first).window

    assert window == Window(start=first.fired_at, end=last.fired_at)
