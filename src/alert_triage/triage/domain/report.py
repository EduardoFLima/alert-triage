"""What one incident is worth telling a team, and how that is worded.

Two halves, and the line between them moved in this slice. Which report an
incident has earned is triage's — that is a question about the incident, the
alerts absorbed into it, and whether an investigation ever completed. What the
investigation has to say for itself is the investigation's, arriving already
worded, because wording a hypothesis is the work of the context that formed it.

So this reads a diagnosis' headline and account and nothing beneath them. It no
longer knows what a finding is, what evidence looks like, or which signals a
deployment's crew covers — the last of which it used to be told by the
composition root, and which an investigation can now state for itself because
what it consulted is a fact it kept.

Delivering what comes out is the notification context's work, and
``TriageReport`` is the contract it publishes for the purpose.
"""

from alert_triage.configuration.settings import ScopedService
from alert_triage.investigation.contract import Diagnosis
from alert_triage.notification.contract import TriageReport
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.incident import Incident

NOT_INVESTIGATED = (
    "Investigation was attempted for these alerts and could not complete. This "
    "report lists what fired and nothing more."
)

NO_TITLE = "(no title reported)"
NO_LINK = "(no link reported)"

SUBJECT_PREFIX = "[alert-triage]"
"""What marks every subject as this system's, whoever wrote the rest of it.

Triage's rather than the investigation's: it identifies the sender, which is a
fact about the run and not about what was found.
"""

CRITICAL_MARKER = "[critical]"
"""What marks a subject as being about a service its operators called critical.

Beside ``SUBJECT_PREFIX`` and for the same reason: whether a service is
critical is a configuration fact about the service, not something an
investigation found, so it is not the Report agent's to write. It changes how a
report reads and nothing else — not when one is delivered, not which channels
carry it, and not how long its cooldown runs.
"""


def build_report(
    incident: Incident, diagnosis: Diagnosis | None, service: ScopedService
) -> TriageReport:
    """Build the report an incident has earned, given what was learned about it.

    The presence of a diagnosis is the whole decision. ``None`` means no
    investigation of this incident ever completed, which is the only case the
    pass-through report is for; a diagnosis with no findings means one completed
    and found nothing, which is a result and reads as one. Why an investigation
    failed, and how many attempts it took to give up, are the run's business and
    never change what a report says.

    Args:
        incident: The incident to report.
        diagnosis: What the investigation came back with, or ``None`` when none
            completed.
        service: What the scope says about the incident's service, which is
            what says whether the subject is marked critical.

    Returns:
        The report to deliver.
    """
    if diagnosis is None:
        return _build_pass_through_report(incident, service)
    return _build_investigated_report(incident, diagnosis, service)


def _build_pass_through_report(
    incident: Incident, service: ScopedService
) -> TriageReport:
    """Build the report an incident gets when nothing could look at it.

    It carries the incident's own alerts and no conclusion of any kind, which is
    what its body says in as many words: passing alerts along untouched is the
    honest thing to do when nothing has managed to look at them.

    Args:
        incident: The incident to report, with the alerts absorbed so far.
        service: What the scope says about its service, which marks the
            subject where the service is a critical one.

    Returns:
        A report naming the service and listing every alert on record for it.
    """
    return TriageReport(
        incident_id=incident.id,
        service=incident.service,
        subject=_subject(incident, service),
        body=_body(incident),
    )


def _build_investigated_report(
    incident: Incident, diagnosis: Diagnosis, service: ScopedService
) -> TriageReport:
    """Build the report for an incident an investigation actually looked at.

    The headline is used as it stands. A diagnosis refuses one spanning more
    than a line, so flattening it here would be defending against a value that
    cannot reach this function — and a guard with no way to fire is a guard
    nobody can trust.

    Carries the investigation's account whole and adds what only triage knows:
    which alerts fired, when, and where to open them. The account already holds
    the conclusion, the findings, and the evidence beneath them, in that order,
    so a reader meets the hypothesis and what it rests on before the alerts that
    prompted looking.

    Args:
        incident: The incident to report, with the alerts absorbed so far.
        diagnosis: What the investigation found and concluded.
        service: What the scope says about its service, which marks the
            subject where the service is a critical one.

    Returns:
        A report announcing the incident in the investigation's own words and
        listing every alert on record.
    """
    return TriageReport(
        incident_id=incident.id,
        service=incident.service,
        subject=f"{_marked(service)} {diagnosis.headline}",
        body=_investigated_body(incident, diagnosis),
    )


def _investigated_body(incident: Incident, diagnosis: Diagnosis) -> str:
    """Lead with what the investigation said, then the alerts that prompted it."""
    lines = [
        f"{_alert_count(len(incident.alerts))} fired for service "
        f"{incident.service} since {incident.window.start.isoformat()}.",
        "",
        diagnosis.account,
        "",
        "Alerts:",
        *(_alert_line(alert) for alert in incident.alerts),
    ]
    return "\n".join(lines)


def _subject(incident: Incident, service: ScopedService) -> str:
    """Announce the incident in the one line every channel can carry."""
    return (
        f"{_marked(service)} {_one_line(incident.service)}: "
        f"{_alert_count(len(incident.alerts))} awaiting triage"
    )


def _marked(service: ScopedService) -> str:
    """What every subject opens with: the sender, and criticality where it holds."""
    if not service.critical:
        return SUBJECT_PREFIX
    return f"{SUBJECT_PREFIX} {CRITICAL_MARKER}"


def _body(incident: Incident) -> str:
    """Say what fired, when, and where to look — and that nobody has looked."""
    lines = [
        f"{_alert_count(len(incident.alerts))} fired for service "
        f"{incident.service} since {incident.window.start.isoformat()}.",
        "",
        NOT_INVESTIGATED,
        "",
        *(_alert_line(alert) for alert in incident.alerts),
    ]
    return "\n".join(lines)


def _alert_line(alert: Alert) -> str:
    """One alert, with the defaults ``Alert`` allows spelled out rather than blank."""
    return (
        f"- {alert.fired_at.isoformat()} | {alert.title or NO_TITLE} | "
        f"{alert.link or NO_LINK}"
    )


def _alert_count(count: int) -> str:
    """Count the alerts in words a subject line and a first sentence can share."""
    return f"{count} alert" if count == 1 else f"{count} alerts"


def _one_line(value: str) -> str:
    """Flatten anything a tag or an agent produced into a subject-safe fragment."""
    return " ".join(value.split())
