from datetime import UTC, datetime, timedelta

from alert_triage.domain.alert import Alert
from alert_triage.domain.grouping import group_alerts

WINDOW = timedelta(minutes=5)
NOON = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def test_alerts_sharing_a_service_within_the_window_form_one_group() -> None:
    first = Alert(service="checkout", raised_at=NOON)
    second = Alert(service="checkout", raised_at=NOON + timedelta(minutes=2))

    groups = group_alerts([first, second], window=WINDOW)

    assert len(groups) == 1
    assert set(groups[0].alerts) == {first, second}


def test_alerts_of_different_services_never_share_a_group() -> None:
    checkout = Alert(service="checkout", raised_at=NOON)
    payments = Alert(service="payments", raised_at=NOON)

    groups = group_alerts([checkout, payments], window=WINDOW)

    assert len(groups) == 2
    assert {group.service for group in groups} == {"checkout", "payments"}


def test_alerts_further_apart_than_the_window_form_separate_groups() -> None:
    early = Alert(service="checkout", raised_at=NOON)
    late = Alert(service="checkout", raised_at=NOON + timedelta(minutes=6))

    groups = group_alerts([early, late], window=WINDOW)

    assert len(groups) == 2
    assert [group.alerts for group in groups] == [(early,), (late,)]


def test_an_alert_exactly_one_window_away_still_groups() -> None:
    first = Alert(service="checkout", raised_at=NOON)
    second = Alert(service="checkout", raised_at=NOON + WINDOW)

    groups = group_alerts([first, second], window=WINDOW)

    assert len(groups) == 1


def test_three_alerts_in_one_incident_are_exposed_as_a_single_group() -> None:
    alerts = [
        Alert(service="checkout", raised_at=NOON + timedelta(minutes=minute))
        for minute in (0, 3, 6)
    ]

    groups = group_alerts(alerts, window=WINDOW)

    assert len(groups) == 1
    assert groups[0].alerts == tuple(alerts)


def test_grouping_no_alerts_yields_no_groups() -> None:
    assert group_alerts([], window=WINDOW) == []


def test_a_group_carries_the_window_its_alerts_span() -> None:
    alerts = [
        Alert(service="checkout", raised_at=NOON),
        Alert(service="checkout", raised_at=NOON + timedelta(minutes=4)),
    ]

    (group,) = group_alerts(alerts, window=WINDOW)

    assert group.started_at == NOON
    assert group.last_seen_at == NOON + timedelta(minutes=4)
