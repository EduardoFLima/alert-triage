"""Triage owns report selection; investigation owns the diagnosis wording."""

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


def build_report(
    incident: Incident, diagnosis: Diagnosis | None, env: str
) -> TriageReport:
    """``None`` means no investigation completed; an empty diagnosis still did."""
    if diagnosis is None:
        return _build_pass_through_report(incident, env)
    return _build_investigated_report(incident, diagnosis, env)


def _build_pass_through_report(incident: Incident, env: str) -> TriageReport:
    return TriageReport(
        incident_id=incident.id,
        service=incident.service,
        subject=_subject(incident, env),
        body=_body(incident, env),
    )


def _build_investigated_report(
    incident: Incident, diagnosis: Diagnosis, env: str
) -> TriageReport:
    return TriageReport(
        incident_id=incident.id,
        service=incident.service,
        subject=f"{_prefix(env)} {diagnosis.headline}",
        body=_investigated_body(incident, diagnosis, env),
    )


def _investigated_body(incident: Incident, diagnosis: Diagnosis, env: str) -> str:
    lines = [
        _what_fired(incident, env),
        "",
        diagnosis.account,
        "",
        "Alerts:",
        *(_alert_line(alert) for alert in incident.alerts),
    ]
    return "\n".join(lines)


def _prefix(env: str) -> str:
    return f"{SUBJECT_PREFIX} [{_one_line(env)}]"


def _subject(incident: Incident, env: str) -> str:
    return (
        f"{_prefix(env)} {_one_line(incident.service)}: "
        f"{_alert_count(len(incident.alerts))} awaiting triage"
    )


def _what_fired(incident: Incident, env: str) -> str:
    return (
        f"{_alert_count(len(incident.alerts))} fired for service "
        f"{incident.service} in {env} since {incident.window.start.isoformat()}."
    )


def _body(incident: Incident, env: str) -> str:
    lines = [
        _what_fired(incident, env),
        "",
        NOT_INVESTIGATED,
        "",
        *(_alert_line(alert) for alert in incident.alerts),
    ]
    return "\n".join(lines)


def _alert_line(alert: Alert) -> str:
    return (
        f"- {alert.fired_at.isoformat()} | {alert.title or NO_TITLE} | "
        f"{alert.link or NO_LINK}"
    )


def _alert_count(count: int) -> str:
    return f"{count} alert" if count == 1 else f"{count} alerts"


def _one_line(value: str) -> str:
    return " ".join(value.split())
