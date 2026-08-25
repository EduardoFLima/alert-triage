"""The report both live channels put over a real socket."""

from datetime import UTC, datetime

import pytest

from alert_triage.notification.contract import TriageReport

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def report() -> TriageReport:
    """One report to put over a real socket, the same for either channel."""
    return TriageReport(
        incident_id="incident-1",
        service="checkout",
        subject="checkout is failing",
        body="Two alerts in thirty minutes.",
    )
