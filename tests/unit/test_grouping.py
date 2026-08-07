from datetime import UTC, datetime, timedelta

from alert_triage.domain.alert import Alert
from alert_triage.domain.grouping import group_alerts

WINDOW = timedelta(minutes=5)
NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def _alert(service: str, offset: timedelta = timedelta()) -> Alert:
    return Alert(service=service, fired_at=NOON + offset)


def test_same_service_within_window_is_one_group() -> None:
    first = _alert("checkout")
    second = _alert("checkout", timedelta(minutes=1))

    groups = group_alerts([first, second], window=WINDOW)

    assert len(groups) == 1
    assert set(groups[0].alerts) == {first, second}
    assert groups[0].service == "checkout"


def test_different_services_never_group_together() -> None:
    checkout = _alert("checkout")
    payments = _alert("payments")

    groups = group_alerts([checkout, payments], window=WINDOW)

    assert len(groups) == 2
    assert {group.service for group in groups} == {"checkout", "payments"}


def test_same_service_outside_window_is_two_groups() -> None:
    first = _alert("checkout")
    later = _alert("checkout", WINDOW + timedelta(seconds=1))

    groups = group_alerts([first, later], window=WINDOW)

    assert len(groups) == 2
    assert [group.alerts for group in groups] == [(first,), (later,)]


def test_alerts_at_exactly_the_window_boundary_group_together() -> None:
    first = _alert("checkout")
    boundary = _alert("checkout", WINDOW)

    groups = group_alerts([first, boundary], window=WINDOW)

    assert len(groups) == 1


def test_group_is_the_unit_downstream_sees_not_the_alert() -> None:
    alerts = [
        _alert("checkout"),
        _alert("checkout", timedelta(minutes=1)),
        _alert("checkout", timedelta(minutes=2)),
    ]

    groups = group_alerts(alerts, window=WINDOW)

    assert len(groups) == 1
    assert len(groups[0].alerts) == 3


def test_alerts_arriving_out_of_order_still_group() -> None:
    late = _alert("checkout", timedelta(minutes=2))
    early = _alert("checkout")

    groups = group_alerts([late, early], window=WINDOW)

    assert len(groups) == 1
    assert groups[0].alerts == (early, late)


def test_no_alerts_yields_no_groups() -> None:
    assert group_alerts([], window=WINDOW) == []
