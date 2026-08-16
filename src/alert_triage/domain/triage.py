"""Deciding which incident a freshly grouped set of alerts belongs to.

Grouping answers "which alerts are one incident *in this run*". This module
answers the same question across runs: a group either continues an incident
already on record or opens a new one. The predicate is deliberately the one
``group_alerts`` applies inside a run — shared service, and alerts no further
apart than the grouping window — so a burst that straddles a run boundary
produces the incident it would have produced had it arrived all at once.

A decision says *whether* an incident is due to be reported, never that it has
been: ``Incident.reported`` is applied by the caller once a channel has
accepted the report, so a delivery that fails leaves the cooldown running from
the last report somebody actually received.

Nothing here reads a clock or generates an identifier of its own: both are
arguments, which is what makes every rule below decidable in a test at any
instant.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from alert_triage.domain.grouping import AlertGroup
from alert_triage.domain.incident import Incident


@dataclass(frozen=True)
class TriageDecision:
    """What a run should do with one group of alerts.

    Attributes:
        incident: The incident the group belongs to, with its new alerts
            absorbed and its last-reported instant as it was. This is the
            value to record — stamped by the caller if a report is delivered.
        should_report: Whether this incident is due to be reported now.
    """

    incident: Incident
    should_report: bool


def triage(
    group: AlertGroup,
    known: Iterable[Incident],
    *,
    now: datetime,
    window: timedelta,
    cooldown: timedelta,
    new_id: Callable[[], str],
) -> TriageDecision:
    """Decide which incident a group belongs to, and whether to report it.

    An incident is reported when it opens, and then not again until the
    cooldown has elapsed since its last report. Suppressing a report never
    suppresses the alerts: they are absorbed either way, so the incident's
    record stays complete for the report that eventually goes out.

    The returned incident is never stamped as reported. That stamp belongs to
    the delivery, which has not happened yet when this returns.

    Args:
        group: The alerts one run grouped, oldest first.
        known: The open incidents on record for the group's service.
        now: The instant to decide against. Supplied rather than read, so the
            same inputs always reach the same decision.
        window: The grouping window, applied here across runs.
        cooldown: How long a report suppresses the next one.
        new_id: Supplies the identifier a newly opened incident is named with.

    Returns:
        The resulting incident and whether it is due to be reported.
    """
    incident = continue_or_open(group, known, window=window, new_id=new_id)
    return TriageDecision(
        incident=incident, should_report=_is_due(incident, now, cooldown)
    )


def _is_due(incident: Incident, now: datetime, cooldown: timedelta) -> bool:
    """Whether enough has elapsed since the last report — never reported counts."""
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
    """Whether an incident can still affect any decision.

    An incident closes once it can neither be continued — its latest alert is
    further back than the grouping window — nor suppress a report, its last
    report being further back than the cooldown. Both bounds already exist, so
    closing needs no setting of its own. A closure already stamped stands: it
    is a fact about a moment, not a recomputation, so retuning the cooldown
    afterwards does not reopen an incident or move when it closed.

    Args:
        incident: The incident to judge.
        now: The instant to judge it at.
        window: The grouping window, which bounds continuation.
        cooldown: How long a report suppresses the next one.

    Returns:
        Whether the incident has closed.
    """
    if incident.closed_at is not None:
        return True
    return now - incident.latest_alert_at > window and _is_due(incident, now, cooldown)


def continue_or_open(
    group: AlertGroup,
    known: Iterable[Incident],
    *,
    window: timedelta,
    new_id: Callable[[], str],
) -> Incident:
    """Place a group of alerts in the incident it belongs to.

    Args:
        group: The alerts one run grouped, oldest first.
        known: The incidents already on record. Closed ones take no part.
        window: The grouping window, applied here across runs.
        new_id: Supplies the identifier a newly opened incident is named with.

    Returns:
        The incident on record with the group's new alerts absorbed, or a
        newly opened incident when the group continues nothing.
    """
    continued = _continued_by(group, known, window)
    if continued is None:
        return Incident(id=new_id(), service=group.service, alerts=group.alerts)
    return continued.absorb(group.alerts)


def _continued_by(
    group: AlertGroup, known: Iterable[Incident], window: timedelta
) -> Incident | None:
    """Find the open incident this group carries on, if there is one."""
    for incident in known:
        if incident.closed_at is None and _continues(incident, group, window):
            return incident
    return None


def _continues(incident: Incident, group: AlertGroup, window: timedelta) -> bool:
    """Whether this group is more of the same incident.

    Sharing an alert identifier settles it without any timing argument, which
    is what makes overlapping ingestion windows cheap. Failing that, the group
    continues the incident when its earliest alert fired no further from the
    incident's latest alert than the grouping window allows.
    """
    if incident.service != group.service:
        return False
    if incident.shares_an_alert_with(group.alerts):
        return True
    return group.alerts[0].fired_at - incident.latest_alert_at <= window
