"""Deciding which alerts describe the same incident.

Alerts arrive one per monitor firing; incidents do not. Grouping is what
turns a burst of firings into the single unit that gets investigated and
reported once.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from alert_triage.domain.alert import Alert


@dataclass(frozen=True, slots=True)
class AlertGroup:
    """The alerts of one service that are treated as a single incident.

    Attributes:
        service: The service tag every alert in the group shares.
        alerts: The grouped alerts, oldest first.
    """

    service: str
    alerts: tuple[Alert, ...]

    @property
    def started_at(self) -> datetime:
        """When the incident's earliest alert fired."""
        return self.alerts[0].raised_at

    @property
    def last_seen_at(self) -> datetime:
        """When the incident's most recent alert fired."""
        return self.alerts[-1].raised_at


def group_alerts(alerts: Iterable[Alert], *, window: timedelta) -> list[AlertGroup]:
    """Group alerts that share a service and fall within the same window.

    A gap longer than ``window`` between consecutive alerts of a service
    starts a new incident. Consecutive rather than pairwise: a service
    alerting steadily every minute for an hour is one incident a human
    investigates once, not sixty.

    Args:
        alerts: The alerts to group, in any order.
        window: How close in time two consecutive alerts of the same service
            must be to belong to the same incident.

    Returns:
        One group per incident, ordered by the service tag and then by when
        the incident started.
    """
    groups: list[AlertGroup] = []
    for service, service_alerts in _by_service(alerts).items():
        groups.extend(
            AlertGroup(service=service, alerts=tuple(run))
            for run in _split_on_gaps(service_alerts, window)
        )
    return groups


def _by_service(alerts: Iterable[Alert]) -> dict[str, list[Alert]]:
    """Bucket alerts by service tag, each bucket ordered oldest first."""
    buckets: dict[str, list[Alert]] = {}
    for alert in sorted(alerts, key=lambda alert: (alert.service, alert.raised_at)):
        buckets.setdefault(alert.service, []).append(alert)
    return buckets


def _split_on_gaps(alerts: list[Alert], window: timedelta) -> list[list[Alert]]:
    """Split time-ordered alerts wherever the gap exceeds the window."""
    runs: list[list[Alert]] = []
    for alert in alerts:
        if runs and alert.raised_at - runs[-1][-1].raised_at <= window:
            runs[-1].append(alert)
        else:
            runs.append([alert])
    return runs
