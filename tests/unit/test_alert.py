from datetime import UTC, datetime

import pytest

from alert_triage.domain.alert import Alert


def test_alert_exposes_the_fields_grouping_reads() -> None:
    fired_at = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)

    alert = Alert(service="checkout", fired_at=fired_at)

    assert alert.service == "checkout"
    assert alert.fired_at == fired_at


def test_alert_is_immutable() -> None:
    alert = Alert(service="checkout", fired_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC))

    with pytest.raises(AttributeError):
        alert.service = "payments"  # type: ignore[misc]
