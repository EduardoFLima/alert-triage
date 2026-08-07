"""Deciding which alerts are the same incident.

Alerts belong to one incident when they share a service tag and fall within
the same time window. The window is a parameter rather than a constant here:
it is an operator-tunable config value, and the domain must not know where
config comes from.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from itertools import groupby

from alert_triage.domain.alert import Alert


@dataclass(frozen=True)
class AlertGroup:
    """The alerts of one incident — the unit that is investigated and reported.

    Attributes:
        service: Service tag shared by every alert in the group.
        alerts: The grouped alerts, oldest first.
    """

    service: str
    alerts: tuple[Alert, ...]


def group_alerts(alerts: Iterable[Alert], window: timedelta) -> list[AlertGroup]:
    """Group alerts into incidents by service tag and time window.

    Within a service, alerts are walked oldest first and a new group starts
    where the gap to the previous alert exceeds ``window``. A sustained burst
    of alerts is therefore one incident rather than one per window-length,
    which is what "investigated and reported once" asks for.

    Args:
        alerts: The alerts to group, in any order.
        window: How far apart two consecutive alerts of the same service may
            fire and still count as the same incident.

    Returns:
        One group per incident, ordered by service then by first alert.
    """
    ordered = sorted(alerts, key=lambda alert: (alert.service, alert.fired_at))
    return [
        AlertGroup(service=service, alerts=tuple(run))
        for service, service_alerts in groupby(ordered, key=lambda alert: alert.service)
        for run in _runs_within(list(service_alerts), window)
    ]


def _runs_within(alerts: list[Alert], window: timedelta) -> list[list[Alert]]:
    """Split time-ordered alerts wherever the gap to the previous one is too wide."""
    runs: list[list[Alert]] = []
    for alert in alerts:
        if runs and alert.fired_at - runs[-1][-1].fired_at <= window:
            runs[-1].append(alert)
        else:
            runs.append([alert])
    return runs
