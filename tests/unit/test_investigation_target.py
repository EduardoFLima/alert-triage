from datetime import UTC, datetime, timedelta

from alert_triage.domain.investigation_target import InvestigationTarget
from alert_triage.domain.window import Window

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
