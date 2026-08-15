"""Fixtures shared by the live-channel integration tests."""

import socket
from datetime import UTC, datetime

import pytest

from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident
from alert_triage.domain.report import TriageReport

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def report() -> TriageReport:
    """One report to put over a real socket, the same for either channel."""
    return TriageReport(
        incident=Incident(
            id="incident-1",
            service="checkout",
            alerts=(Alert(service="checkout", fired_at=NOON, source_id="a"),),
        ),
        subject="checkout is failing",
        body="Two alerts in thirty minutes.",
    )


@pytest.fixture
def free_port() -> int:
    """A port nothing is listening on, found by binding one and letting it go."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
