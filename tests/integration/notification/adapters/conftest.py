from datetime import UTC, datetime

import pytest

from alert_triage.notification.contract import TriageReport

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def report() -> TriageReport:
    return TriageReport(
        incident_id="incident-1",
        service="checkout",
        subject="checkout is failing",
        body="Two alerts in thirty minutes.",
    )
