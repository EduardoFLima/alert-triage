from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.domain.findings import LogRecord
from alert_triage.domain.window import Window
from alert_triage.ports.observability_platform import (
    ObservabilityPlatform,
    ObservabilityPlatformError,
)

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
WINDOW = Window(start=NOON, end=NOON + timedelta(minutes=7))


class _Platform:
    """Everything the port asks of an implementation, and nothing more."""

    def search_logs(
        self, service: str, window: Window, query: str
    ) -> Sequence[LogRecord]:
        return ()


def test_an_implementation_needs_only_the_ports_own_vocabulary() -> None:
    assert isinstance(_Platform(), ObservabilityPlatform)


def test_something_without_the_search_is_not_a_platform() -> None:
    class _NotAPlatform:
        pass

    assert not isinstance(_NotAPlatform(), ObservabilityPlatform)


def test_the_failure_is_defined_beside_the_port() -> None:
    """A caller distinguishes 'no logs' from 'the search failed' without an adapter."""
    with pytest.raises(ObservabilityPlatformError):
        raise ObservabilityPlatformError("the platform refused the request")


def test_a_platform_answers_in_domain_records() -> None:
    found = _Platform().search_logs("checkout", WINDOW, "status:error")

    assert all(isinstance(record, LogRecord) for record in found)
