from datetime import UTC, datetime

import pytest

from alert_triage.triage.domain.alert import Alert


def test_alert_exposes_the_fields_grouping_reads() -> None:
    fired_at = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)

    alert = Alert(service="checkout", fired_at=fired_at)

    assert alert.service == "checkout"
    assert alert.fired_at == fired_at


def test_alert_carries_identity_and_provenance() -> None:
    alert = Alert(
        service="checkout",
        fired_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
        source_id="evt-1",
        title="Checkout latency above threshold",
        link="https://app.datadoghq.com/event/event?id=evt-1",
    )

    assert alert.source_id == "evt-1"
    assert alert.title == "Checkout latency above threshold"
    assert alert.link == "https://app.datadoghq.com/event/event?id=evt-1"


def test_alert_carries_the_latency_that_triggered_it() -> None:
    alert = Alert(
        service="checkout",
        fired_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
        observed_latency_ms=1400,
    )

    assert alert.observed_latency_ms == 1400


def test_an_alert_nobody_measured_carries_no_latency() -> None:
    """Absent and zero are opposite evidence, so they must not read alike."""
    unmeasured = Alert(
        service="checkout", fired_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    )
    measured = Alert(
        service="checkout",
        fired_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
        observed_latency_ms=0,
    )

    assert unmeasured.observed_latency_ms is None
    assert measured.observed_latency_ms == 0


def test_alert_is_immutable() -> None:
    alert = Alert(service="checkout", fired_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC))

    with pytest.raises(AttributeError):
        alert.service = "payments"  # type: ignore[misc]
