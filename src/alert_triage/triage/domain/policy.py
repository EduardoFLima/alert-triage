"""Carry alert grouping across runs; delivery owns the reported stamp."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from alert_triage.triage.domain.grouping import AlertGroup
from alert_triage.triage.domain.incident import Incident


@dataclass(frozen=True)
class TriageDecision:
    incident: Incident
    should_report: bool
    should_investigate: bool


def triage(
    group: AlertGroup,
    known: Iterable[Incident],
    *,
    now: datetime,
    window: timedelta,
    cooldown: timedelta,
    max_attempts: int,
    new_id: Callable[[], str],
) -> TriageDecision:
    """Suppressing a report never suppresses the alerts."""
    if max_attempts < 1:
        raise ValueError("max_attempts must allow at least one investigation")
    incident = continue_or_open(group, known, window=window, new_id=new_id)
    should_report = _is_due(incident, now, cooldown)
    return TriageDecision(
        incident=incident,
        should_report=should_report,
        should_investigate=should_report
        and incident.investigation_attempts < max_attempts,
    )


def _is_due(incident: Incident, now: datetime, cooldown: timedelta) -> bool:
    if incident.last_reported_at is None:
        return True
    return now - incident.last_reported_at >= cooldown


def is_closed(
    incident: Incident,
    *,
    now: datetime,
    window: timedelta,
    cooldown: timedelta,
) -> bool:
    """Never close an unreported incident; it still owes a report or a bounded retry."""
    if incident.closed_at is not None:
        return True
    if incident.last_reported_at is None:
        return False
    return now - incident.window.end > window and _is_due(incident, now, cooldown)


def continue_or_open(
    group: AlertGroup,
    known: Iterable[Incident],
    *,
    window: timedelta,
    new_id: Callable[[], str],
) -> Incident:
    continued = _continued_by(group, known, window)
    if continued is None:
        return Incident(id=new_id(), service=group.service, alerts=group.alerts)
    return continued.absorb(group.alerts)


def _continued_by(
    group: AlertGroup, known: Iterable[Incident], window: timedelta
) -> Incident | None:
    for incident in known:
        if incident.closed_at is None and _continues(incident, group, window):
            return incident
    return None


def _continues(incident: Incident, group: AlertGroup, window: timedelta) -> bool:
    """Shared alert ids settle overlapping ingestion windows without timing."""
    if incident.service != group.service:
        return False
    if incident.shares_an_alert_with(group.alerts):
        return True
    return group.alerts[0].fired_at - incident.window.end <= window
