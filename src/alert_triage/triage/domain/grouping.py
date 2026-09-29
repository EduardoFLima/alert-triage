from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from itertools import groupby

from alert_triage.triage.domain.alert import Alert


@dataclass(frozen=True)
class AlertGroup:
    service: str
    alerts: tuple[Alert, ...]


def group_alerts(alerts: Iterable[Alert], window: timedelta) -> list[AlertGroup]:
    """A sustained burst is one incident, not one incident per window length."""
    ordered = sorted(alerts, key=lambda alert: (alert.service, alert.fired_at))
    return [
        AlertGroup(service=service, alerts=tuple(run))
        for service, service_alerts in groupby(ordered, key=lambda alert: alert.service)
        for run in _runs_within(list(service_alerts), window)
    ]


def _runs_within(alerts: list[Alert], window: timedelta) -> list[list[Alert]]:
    runs: list[list[Alert]] = []
    for alert in alerts:
        if runs and alert.fired_at - runs[-1][-1].fired_at <= window:
            runs[-1].append(alert)
        else:
            runs.append([alert])
    return runs
