from datetime import UTC, datetime

import pytest

from alert_triage.domain.alert import Alert


def test_alert_exposes_the_service_tag_and_timestamp_it_was_built_from() -> None:
    raised_at = datetime(2026, 8, 4, 9, 30, tzinfo=UTC)

    alert = Alert(service="checkout", raised_at=raised_at)

    assert alert.service == "checkout"
    assert alert.raised_at == raised_at


def test_alert_is_immutable() -> None:
    alert = Alert(service="checkout", raised_at=datetime(2026, 8, 4, tzinfo=UTC))

    with pytest.raises(AttributeError):
        alert.service = "payments"  # type: ignore[misc]
