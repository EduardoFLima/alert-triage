from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.domain.alert import Alert
from alert_triage.domain.grouping import AlertGroup, group_alerts
from alert_triage.domain.incident import Incident
from alert_triage.domain.triage import (
    TriageDecision,
    continue_or_open,
    is_closed,
    triage,
)

WINDOW = timedelta(minutes=30)
COOLDOWN = timedelta(days=2)
MAX_ATTEMPTS = 3
NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def _alert(
    source_id: str, offset: timedelta = timedelta(), service: str = "checkout"
) -> Alert:
    return Alert(service=service, fired_at=NOON + offset, source_id=source_id)


def _group(*alerts: Alert) -> AlertGroup:
    return AlertGroup(service=alerts[0].service, alerts=alerts)


def _ids() -> Callable[[], str]:
    """Deterministic identifiers, so a test can name the incident it expects."""
    counter = iter(range(1, 100))
    return lambda: f"incident-{next(counter)}"


def _on_record(*alerts: Alert, incident_id: str = "incident-0") -> Incident:
    return Incident(
        id=incident_id,
        service=alerts[0].service,
        alerts=alerts,
        last_reported_at=NOON,
    )


def test_a_group_of_alerts_already_absorbed_continues_its_incident() -> None:
    """The lookback window is wider than the run interval, so runs overlap."""
    seen = _alert("a")
    incident = _on_record(seen)

    resulting = continue_or_open(_group(seen), [incident], window=WINDOW, new_id=_ids())

    assert resulting.id == incident.id
    assert resulting.alerts == incident.alerts


def test_a_firing_incident_absorbs_only_the_alerts_it_has_not_seen() -> None:
    seen = _alert("a")
    fresh = _alert("b", timedelta(minutes=5))
    incident = _on_record(seen)

    resulting = continue_or_open(
        _group(seen, fresh), [incident], window=WINDOW, new_id=_ids()
    )

    assert resulting.id == incident.id
    assert resulting.alerts == (seen, fresh)
    assert resulting.window.end == fresh.fired_at


def test_a_burst_straddling_two_runs_is_the_incident_it_would_have_been() -> None:
    """Continuation is the grouping rule asked again a run later."""
    first_run = [_alert("a"), _alert("b", timedelta(minutes=10))]
    second_run = [_alert("c", timedelta(minutes=25))]
    incident = _on_record(*first_run)

    resulting = continue_or_open(
        _group(*second_run), [incident], window=WINDOW, new_id=_ids()
    )

    (in_one_go,) = group_alerts(first_run + second_run, window=WINDOW)
    assert resulting.id == incident.id
    assert resulting.alerts == in_one_go.alerts


def test_alerts_further_off_than_the_window_open_a_new_incident() -> None:
    incident = _on_record(_alert("a"))
    separate = _alert("b", WINDOW + timedelta(seconds=1))

    resulting = continue_or_open(
        _group(separate), [incident], window=WINDOW, new_id=_ids()
    )

    assert resulting.id == "incident-1"
    assert resulting.alerts == (separate,)


def test_two_incidents_on_one_service_are_told_apart() -> None:
    incident = _on_record(_alert("a"))
    separate = _alert("b", WINDOW + timedelta(seconds=1))

    resulting = continue_or_open(
        _group(separate), [incident], window=WINDOW, new_id=_ids()
    )

    assert resulting.id != incident.id


def test_alerts_for_a_service_with_nothing_on_record_open_an_incident() -> None:
    opening = _alert("a")

    resulting = continue_or_open(_group(opening), [], window=WINDOW, new_id=_ids())

    assert resulting.id == "incident-1"
    assert resulting.service == "checkout"
    assert resulting.alerts == (opening,)
    assert resulting.last_reported_at is None


def test_an_incident_on_another_service_is_never_continued() -> None:
    incident = _on_record(_alert("a"))
    elsewhere = _alert("b", timedelta(minutes=1), service="payments")

    resulting = continue_or_open(
        _group(elsewhere), [incident], window=WINDOW, new_id=_ids()
    )

    assert resulting.id == "incident-1"
    assert resulting.service == "payments"


def _decide(
    group: AlertGroup,
    known: list[Incident],
    at: datetime,
    cooldown: timedelta = COOLDOWN,
) -> tuple[Incident, bool]:
    decision = triage(
        group,
        known,
        now=at,
        window=WINDOW,
        cooldown=cooldown,
        max_attempts=MAX_ATTEMPTS,
        new_id=_ids(),
    )
    return decision.incident, decision.should_report


def test_a_newly_opened_incident_is_reported() -> None:
    opening = _alert("a")

    incident, should_report = _decide(_group(opening), [], at=NOON)

    assert should_report
    assert incident.alerts == (opening,)
    assert incident.last_reported_at is None, "the stamp follows the delivery"


def test_a_continuation_within_the_cooldown_is_suppressed() -> None:
    seen = _alert("a")
    fresh = _alert("b", timedelta(minutes=5))
    incident = _on_record(seen)

    resulting, should_report = _decide(
        _group(seen, fresh), [incident], at=NOON + COOLDOWN - timedelta(seconds=1)
    )

    assert not should_report
    assert resulting.alerts == (seen, fresh), "the alerts are absorbed regardless"
    assert resulting.last_reported_at == NOON, "suppressing does not restart it"


def test_a_continuation_after_the_cooldown_is_reported_again() -> None:
    seen = _alert("a")
    fresh = _alert("b", timedelta(minutes=5))
    incident = _on_record(seen)
    at = NOON + COOLDOWN

    resulting, should_report = _decide(_group(seen, fresh), [incident], at=at)

    assert should_report
    assert resulting.alerts == (seen, fresh)


def test_an_incident_due_again_keeps_the_stamp_of_its_last_report() -> None:
    """Nothing is lost by not stamping: a delivery that fails leaves this stamp."""
    incident = _on_record(_alert("a"))

    resulting, should_report = _decide(
        _group(_alert("b", timedelta(minutes=5))), [incident], at=NOON + COOLDOWN
    )

    assert should_report
    assert resulting.last_reported_at == NOON, "the previous report is still the last"


def test_the_cooldown_is_measured_from_the_most_recent_report() -> None:
    incident = _on_record(_alert("a"))
    second_report_at = NOON + COOLDOWN

    due, _ = _decide(_group(_alert("a")), [incident], at=second_report_at)
    reported = due.reported(second_report_at)
    _, should_report = _decide(
        _group(_alert("b", timedelta(minutes=5))),
        [reported],
        at=second_report_at + timedelta(hours=1),
    )

    assert reported.last_reported_at == second_report_at
    assert not should_report, "an hour after the second report, not two days"


def test_an_incident_in_its_cooldown_does_not_suppress_another_on_the_service() -> None:
    quietened = _on_record(_alert("a"))
    separate = _alert("b", WINDOW + timedelta(seconds=1))

    incident, should_report = _decide(
        _group(separate), [quietened], at=NOON + timedelta(minutes=31)
    )

    assert should_report
    assert incident.id != quietened.id


def test_the_same_inputs_at_the_same_instant_decide_the_same_way() -> None:
    incident = _on_record(_alert("a"))
    group = _group(_alert("b", timedelta(minutes=5)))
    at = NOON + timedelta(hours=1)

    first = _decide(group, [incident], at=at)
    second = _decide(group, [incident], at=at)

    assert first == second


def test_an_instant_past_the_cooldown_reports_without_waiting_for_one() -> None:
    incident = _on_record(_alert("a"))

    _, should_report = _decide(
        _group(_alert("b", timedelta(minutes=5))), [incident], at=NOON + COOLDOWN
    )

    assert should_report


def test_an_incident_past_both_the_window_and_the_cooldown_has_closed() -> None:
    """Closed once it can neither be continued nor suppress a report."""
    incident = _on_record(_alert("a"))

    assert is_closed(
        incident, now=NOON + COOLDOWN + WINDOW, window=WINDOW, cooldown=COOLDOWN
    )


def test_a_quiet_incident_still_inside_its_cooldown_stays_open() -> None:
    """So that a re-fire within the cooldown is still suppressed."""
    incident = _on_record(_alert("a"))

    assert not is_closed(
        incident,
        now=NOON + WINDOW + timedelta(minutes=1),
        window=WINDOW,
        cooldown=COOLDOWN,
    )


def test_an_incident_still_producing_alerts_stays_open() -> None:
    incident = _on_record(_alert("a"))

    assert not is_closed(
        incident, now=NOON + COOLDOWN, window=COOLDOWN, cooldown=COOLDOWN
    )


def test_an_incident_already_stamped_closed_stays_closed() -> None:
    incident = _on_record(_alert("a")).closed(NOON + timedelta(days=3))

    assert is_closed(incident, now=NOON, window=WINDOW, cooldown=COOLDOWN)


def test_a_closed_incident_is_not_continued_by_later_alerts() -> None:
    closed = _on_record(_alert("a")).closed(NOON + timedelta(days=3))
    later = _alert("b", timedelta(minutes=5))

    resulting, _ = _decide(_group(later), [closed], at=NOON + timedelta(days=3))

    assert resulting.id != closed.id
    assert resulting.alerts == (later,)


def test_a_closed_incident_does_not_suppress_a_later_report() -> None:
    closed = _on_record(_alert("a")).closed(NOON + timedelta(minutes=1))

    _, should_report = _decide(
        _group(_alert("b", timedelta(minutes=5))),
        [closed],
        at=NOON + timedelta(hours=1),
    )

    assert should_report, "its last report was well inside the cooldown"


def _investigate(
    group: AlertGroup,
    known: list[Incident],
    at: datetime,
    max_attempts: int = MAX_ATTEMPTS,
) -> TriageDecision:
    return triage(
        group,
        known,
        now=at,
        window=WINDOW,
        cooldown=COOLDOWN,
        max_attempts=max_attempts,
        new_id=_ids(),
    )


def test_a_newly_opened_incident_is_investigated() -> None:
    decision = _investigate(_group(_alert("a")), [], at=NOON)

    assert decision.should_investigate


def test_an_incident_inside_its_cooldown_is_not_investigated() -> None:
    """A suppressed report costs no model spend."""
    incident = _on_record(_alert("a"))

    decision = _investigate(
        _group(_alert("b", timedelta(minutes=5))), [incident], at=NOON
    )

    assert not decision.should_investigate


def test_an_incident_whose_investigation_failed_is_investigated_again() -> None:
    incident = replace(
        _on_record(_alert("a")), last_reported_at=None, investigation_attempts=1
    )

    decision = _investigate(
        _group(_alert("b", timedelta(minutes=5))), [incident], at=NOON
    )

    assert decision.should_investigate


def test_an_incident_that_has_spent_its_attempts_is_not_investigated() -> None:
    """The bound is on the incident, not on retries: an unreachable platform ends."""
    incident = replace(
        _on_record(_alert("a")),
        last_reported_at=None,
        investigation_attempts=MAX_ATTEMPTS,
    )

    decision = _investigate(
        _group(_alert("b", timedelta(minutes=5))), [incident], at=NOON
    )

    assert decision.should_report
    assert not decision.should_investigate


def test_an_overdue_incident_with_attempts_spent_stays_uninvestigated() -> None:
    """However many runs handle it: the cost of a broken platform stays bounded."""
    incident = replace(
        _on_record(_alert("a")),
        last_reported_at=None,
        investigation_attempts=MAX_ATTEMPTS,
    )

    for run in range(5):
        decision = _investigate(
            _group(_alert("b", timedelta(minutes=5))),
            [incident],
            at=NOON + timedelta(hours=run),
        )
        assert not decision.should_investigate


def test_a_single_attempt_disables_retrying() -> None:
    incident = replace(
        _on_record(_alert("a")), last_reported_at=None, investigation_attempts=1
    )

    decision = _investigate(
        _group(_alert("b", timedelta(minutes=5))), [incident], at=NOON, max_attempts=1
    )

    assert not decision.should_investigate


def test_an_attempt_bound_below_one_leaves_an_incident_uninvestigable() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        _investigate(_group(_alert("a")), [], at=NOON, max_attempts=0)


def test_an_incident_never_reported_stays_open_however_quiet_it_goes() -> None:
    """It still owes a report, and a decision it owes is a decision it affects.

    Before investigation could be silent, an incident was reported on the run
    that opened it, so ``last_reported_at`` was always set by the time its
    alerts aged past the window. A failed investigation delivers nothing, so
    now it can go quiet still owing its report — and closing it there would
    discard the attempts it had spent and open a fresh incident next run,
    which is the unbounded spend the attempt bound exists to prevent.
    """
    never_reported = Incident(
        id="incident-0",
        service="checkout",
        alerts=(_alert("a"),),
        last_reported_at=None,
        investigation_attempts=1,
    )

    assert not is_closed(
        never_reported,
        now=NOON + WINDOW + timedelta(hours=2),
        window=WINDOW,
        cooldown=COOLDOWN,
    )


def test_an_incident_reported_and_long_quiet_still_closes() -> None:
    reported = _on_record(_alert("a"))

    assert is_closed(
        reported,
        now=NOON + COOLDOWN + timedelta(seconds=1),
        window=WINDOW,
        cooldown=COOLDOWN,
    )
