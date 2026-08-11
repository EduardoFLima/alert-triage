from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def _alert(offset: timedelta = timedelta(), source_id: str = "") -> Alert:
    return Alert(service="checkout", fired_at=NOON + offset, source_id=source_id)


def _incident(*alerts: Alert) -> Incident:
    return Incident(id="incident-1", service="checkout", alerts=alerts)


def test_an_incident_carries_its_identity_service_and_alerts() -> None:
    opening = _alert()

    incident = _incident(opening)

    assert incident.id == "incident-1"
    assert incident.service == "checkout"
    assert incident.alerts == (opening,)


def test_an_incident_that_has_never_been_reported_says_so() -> None:
    assert _incident(_alert()).last_reported_at is None


def test_the_window_an_incident_spans_is_read_from_its_alerts() -> None:
    """Derived, not stored: two records of the same fact can disagree."""
    first = _alert()
    last = _alert(timedelta(minutes=7))

    incident = _incident(last, first)

    assert incident.started_at == first.fired_at
    assert incident.latest_alert_at == last.fired_at


def test_there_is_no_incident_without_the_alerts_that_opened_it() -> None:
    with pytest.raises(ValueError, match="at least one alert"):
        _incident()


def test_absorbing_alerts_keeps_the_identity_the_incident_opened_with() -> None:
    incident = _incident(_alert(source_id="a"))

    grown = incident.absorb([_alert(timedelta(minutes=3), source_id="b")])

    assert grown.id == incident.id
    assert grown.service == incident.service


def test_absorbing_a_later_alert_extends_the_window() -> None:
    incident = _incident(_alert(source_id="a"))

    grown = incident.absorb([_alert(timedelta(minutes=3), source_id="b")])

    assert grown.started_at == NOON
    assert grown.latest_alert_at == NOON + timedelta(minutes=3)
    assert incident.latest_alert_at == NOON, "the original is left as it stands"


def test_an_alert_already_absorbed_is_not_recorded_twice() -> None:
    """Overlapping ingestion windows re-deliver alerts the incident already has."""
    seen = _alert(source_id="a")
    incident = _incident(seen)

    grown = incident.absorb([seen, _alert(timedelta(minutes=3), source_id="b")])

    assert len(grown.alerts) == 2


def test_an_alert_the_platform_reported_again_is_recognised_by_its_identifier() -> None:
    incident = _incident(_alert(source_id="a"))

    regrouped = Alert(service="checkout", fired_at=NOON, source_id="a", title="retold")
    grown = incident.absorb([regrouped])

    assert len(grown.alerts) == 1


def test_absorbed_alerts_are_kept_oldest_first() -> None:
    incident = _incident(_alert(timedelta(minutes=5), source_id="b"))

    grown = incident.absorb([_alert(source_id="a")])

    assert [alert.source_id for alert in grown.alerts] == ["a", "b"]
