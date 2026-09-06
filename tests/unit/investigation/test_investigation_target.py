from datetime import UTC, datetime, timedelta

from alert_triage.investigation.contract import (
    MINIMUM_EVIDENCE_SPAN,
    InvestigationTarget,
)
from alert_triage.shared.window import Window

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _target(alert_count: int = 2) -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON + timedelta(minutes=7)),
        alert_count=alert_count,
    )


def test_a_target_is_described_by_its_service_and_window() -> None:
    described = _target().describe()

    assert "checkout" in described
    assert NOON.isoformat() in described
    assert (NOON + timedelta(minutes=7)).isoformat() in described


def test_a_target_tells_a_specialist_how_much_fired() -> None:
    """Volume is context a specialist weighs; which alerts they were is not."""
    assert "2" in _target(alert_count=2).describe()


def test_a_target_is_not_critical_unless_it_was_told_so() -> None:
    """A caller that knows nothing of criticality still builds a valid target."""
    assert not _target().critical


def test_a_critical_services_target_says_so_where_the_agents_read_it() -> None:
    target = InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON + timedelta(minutes=7)),
        alert_count=2,
        critical=True,
    )

    assert target.critical
    assert "critical" in target.describe().lower()


def test_a_target_that_is_not_critical_is_stated_plainly() -> None:
    """Silence is not the answer: a reader must be told which of the two it is."""
    described = _target().describe()

    assert "critical" in described.lower()
    assert "not" in described.lower()


def test_a_single_alert_still_gives_the_platform_a_period_it_can_query() -> None:
    """An incident of one alert spans an instant, and no query accepts one."""
    target = InvestigationTarget(
        service="checkout", window=Window(start=NOON, end=NOON), alert_count=1
    )

    assert target.window.end > target.window.start


def test_a_widened_window_still_covers_the_alerts_that_caused_it() -> None:
    """Widening is for context around the problem, not instead of it."""
    target = InvestigationTarget(
        service="checkout", window=Window(start=NOON, end=NOON), alert_count=1
    )

    assert target.window.start <= NOON <= target.window.end


def test_a_window_too_narrow_to_query_is_widened_to_the_minimum() -> None:
    target = InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON + timedelta(seconds=1)),
        alert_count=2,
    )

    assert target.window.end - target.window.start == MINIMUM_EVIDENCE_SPAN


def test_a_window_is_widened_evenly_so_the_alerts_stay_centred() -> None:
    """The lead-up and the aftermath are both worth seeing."""
    target = InvestigationTarget(
        service="checkout", window=Window(start=NOON, end=NOON), alert_count=1
    )

    assert NOON - target.window.start == target.window.end - NOON


def test_a_window_already_wide_enough_is_left_alone() -> None:
    spanning = Window(start=NOON, end=NOON + MINIMUM_EVIDENCE_SPAN * 2)

    target = InvestigationTarget(service="checkout", window=spanning, alert_count=9)

    assert target.window == spanning
