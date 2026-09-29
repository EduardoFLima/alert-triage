from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.shared.window import Window

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


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
