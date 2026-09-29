import inspect
from dataclasses import dataclass, field
from datetime import UTC, datetime

from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.ports.alert_source import AlertSource, AlertSourceError

SINCE = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class InMemoryAlertSource:
    alerts: list[Alert] = field(default_factory=list)

    def fetch_since(self, since: datetime) -> list[Alert]:
        return [alert for alert in self.alerts if alert.fired_at >= since]


def test_the_port_yields_domain_alerts_from_the_requested_instant() -> None:
    recent = Alert(service="checkout", fired_at=SINCE)
    source: AlertSource = InMemoryAlertSource(alerts=[recent])

    fetched = source.fetch_since(SINCE)

    assert isinstance(source, AlertSource)
    assert fetched == [recent]
    assert all(isinstance(alert, Alert) for alert in fetched)


def test_the_fetch_is_synchronous() -> None:
    assert not inspect.iscoroutinefunction(InMemoryAlertSource.fetch_since)
    assert not inspect.iscoroutinefunction(AlertSource.fetch_since)


def test_a_failure_to_fetch_has_one_error_type_to_catch() -> None:
    assert issubclass(AlertSourceError, Exception)
