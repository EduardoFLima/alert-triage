"""The Incident entity: an alert group that has been given a lasting identity.

Grouping recomputes an ``AlertGroup`` from whatever alerts a run fetched, so a
group is only ever a statement about one run. An incident is the same problem
observed across runs: it is named once, absorbs the alerts that keep arriving
for it, and remembers when it was last reported. That is what makes "already
reported" a statement about a problem rather than about a set of alert ids.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime

from alert_triage.domain.alert import Alert
from alert_triage.domain.window import Window


@dataclass(frozen=True)
class Incident:
    """One problem on one service, tracked from the run that first saw it.

    Attributes:
        id: Identifier generated when the incident opened. Opaque, and never
            derived from the alerts, so absorbing new ones leaves it alone.
        service: Service tag shared by every alert in the incident.
        alerts: The alerts absorbed so far, oldest first.
        last_reported_at: When the incident was last reported, or ``None``
            while it has never been reported.
        closed_at: When the incident was observed to have closed, or ``None``
            while it is still open. Stamped once, so retuning the cooldown
            cannot move a closure that already happened.
        investigation_attempts: How many investigations of this incident have
            failed since a report about it was last delivered. Zero means
            nothing is outstanding; it is what bounds retrying, and it survives
            between runs because a retry spans them.
    """

    id: str
    service: str
    alerts: tuple[Alert, ...]
    last_reported_at: datetime | None = None
    closed_at: datetime | None = None
    investigation_attempts: int = 0

    def __post_init__(self) -> None:
        """Reject an incident with no alerts, rather than one spanning no window."""
        if not self.alerts:
            raise ValueError(
                "An incident is the alerts absorbed into it: it needs at least "
                "one alert"
            )
        object.__setattr__(self, "alerts", tuple(sorted(self.alerts, key=_fired_at)))

    @property
    def started_at(self) -> datetime:
        """When the earliest alert of the incident fired."""
        return self.alerts[0].fired_at

    @property
    def latest_alert_at(self) -> datetime:
        """When the most recent alert of the incident fired."""
        return self.alerts[-1].fired_at

    @property
    def window(self) -> Window:
        """The stretch of time the incident's alerts span.

        What an investigation asks the observability platform about: evidence
        is wanted around the alerts, not around the run that happened to fetch
        them.
        """
        return Window(start=self.started_at, end=self.latest_alert_at)

    def absorb(self, alerts: Iterable[Alert]) -> "Incident":
        """Take in the alerts of this incident that are not recorded yet.

        Args:
            alerts: Alerts a run grouped for this incident, re-delivered ones
                included — an ingestion window wider than the run interval
                guarantees some of them have been seen before.

        Returns:
            The incident with the new alerts absorbed, keeping its identity.
        """
        recorded = {_identity(alert) for alert in self.alerts}
        new = tuple(alert for alert in alerts if _identity(alert) not in recorded)
        if not new:
            return self
        return replace(self, alerts=self.alerts + new)

    def reported(self, at: datetime) -> "Incident":
        """Record that the incident has just been reported, restarting its cooldown.

        A delivered report also ends any round of retrying, whatever that
        report carried: either it carried findings, or it was the last-resort
        report sent once the attempts ran out. Either way there is nothing left
        to retry, and the incident earns a fresh allowance if its alerts
        outlast the cooldown.
        """
        return replace(self, last_reported_at=at, investigation_attempts=0)

    def investigation_failed(self) -> "Incident":
        """Record that an investigation of this incident did not complete.

        Spends one of the incident's attempts. Only a failure spends one: an
        investigation that succeeded costs nothing, so a report that then fails
        to deliver leaves the retry owed rather than consuming it.
        """
        return replace(self, investigation_attempts=self.investigation_attempts + 1)

    def closed(self, at: datetime) -> "Incident":
        """Record that the incident was observed closed at this instant."""
        return replace(self, closed_at=at)

    def shares_an_alert_with(self, alerts: Iterable[Alert]) -> bool:
        """Whether any of these alerts is one this incident already absorbed."""
        recorded = {_identity(alert) for alert in self.alerts}
        return any(_identity(alert) in recorded for alert in alerts)


def _identity(alert: Alert) -> object:
    """What makes two alerts the same alert.

    The reporting platform's identifier when there is one — that is what stays
    stable across the runs whose windows overlap. Without one, an alert is only
    recognisable by being identical in every respect.
    """
    return alert.source_id or alert


def _fired_at(alert: Alert) -> datetime:
    return alert.fired_at
