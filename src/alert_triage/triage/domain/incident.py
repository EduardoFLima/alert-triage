from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime

from alert_triage.configuration.settings import Scope
from alert_triage.investigation.contract import InvestigationTarget
from alert_triage.shared.window import Window
from alert_triage.triage.domain.alert import Alert


@dataclass(frozen=True)
class Incident:
    """One named problem across runs, not just one run's alert ids."""

    id: str
    service: str
    alerts: tuple[Alert, ...]
    last_reported_at: datetime | None = None
    closed_at: datetime | None = None
    investigation_attempts: int = 0

    def __post_init__(self) -> None:
        if not self.alerts:
            raise ValueError(
                "An incident is the alerts absorbed into it: it needs at least "
                "one alert"
            )
        object.__setattr__(self, "alerts", tuple(sorted(self.alerts, key=_fired_at)))

    @property
    def window(self) -> Window:
        """Evidence is wanted around the alerts, not the run that fetched them."""
        return Window(start=self.alerts[0].fired_at, end=self.alerts[-1].fired_at)

    def investigation_target(self, scope: Scope) -> InvestigationTarget:
        return InvestigationTarget(
            service=self.service,
            window=self.window,
            alert_count=len(self.alerts),
            critical=scope.for_service(self.service).critical,
            env=scope.env,
        )

    def absorb(self, alerts: Iterable[Alert]) -> "Incident":
        """Ignore re-delivered alerts from overlapping ingestion windows."""
        recorded = {_identity(alert) for alert in self.alerts}
        new = tuple(alert for alert in alerts if _identity(alert) not in recorded)
        if not new:
            return self
        return replace(self, alerts=self.alerts + new)

    def reported(self, at: datetime) -> "Incident":
        """Restart cooldown and end retrying, whatever the report carried."""
        return replace(self, last_reported_at=at, investigation_attempts=0)

    def investigation_failed(self) -> "Incident":
        """Only investigation failures spend attempts; delivery failures do not."""
        return replace(self, investigation_attempts=self.investigation_attempts + 1)

    def closed(self, at: datetime) -> "Incident":
        return replace(self, closed_at=at)

    def shares_an_alert_with(self, alerts: Iterable[Alert]) -> bool:
        recorded = {_identity(alert) for alert in self.alerts}
        return any(_identity(alert) in recorded for alert in alerts)


def _identity(alert: Alert) -> object:
    """Prefer the platform id because it stays stable across overlapping runs."""
    return alert.source_id or alert


def _fired_at(alert: Alert) -> datetime:
    return alert.fired_at
