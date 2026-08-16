"""The TriageReport value: what the system has to say about one incident.

Deliberately thin, and deliberately channel-neutral. A subject and a body of
plain text are what every channel can carry, so rendering — a MIME message, a
card, whatever comes next — stays the adapter's own work and adding a channel
changes nothing about what a report *is*.

The incident travels with the report rather than being flattened into the
text: an identifier is what tells two reports apart, and what something later
attaches an acknowledgement to.
"""

from dataclasses import dataclass

from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident

NOT_INVESTIGATED = (
    "These alerts have not been investigated. This report lists what fired and "
    "nothing more."
)

NO_TITLE = "(no title reported)"
NO_LINK = "(no link reported)"


@dataclass(frozen=True)
class TriageReport:
    """What one incident is worth telling a team, before any channel sees it.

    Attributes:
        incident: The incident the report concerns.
        subject: One line announcing the report, as a subject or a heading.
        body: The report itself, as plain text. Opaque to delivery: a channel
            carries it unchanged, so changing what a report says never means
            adjusting a channel.
    """

    incident: Incident
    subject: str
    body: str

    def __post_init__(self) -> None:
        """Reject a subject no channel could present as the one line it is."""
        if not self.subject.strip():
            raise ValueError("A report needs a subject to announce it")
        if "\n" in self.subject or "\r" in self.subject:
            raise ValueError(
                "A report's subject is a single line: put the detail in the body"
            )

    @property
    def incident_id(self) -> str:
        """Identifier of the incident this report concerns."""
        return self.incident.id

    @property
    def service(self) -> str:
        """Service the incident is about."""
        return self.incident.service


def build_pass_through_report(incident: Incident) -> TriageReport:
    """Build the report the system sends while investigation does not exist yet.

    It carries the incident's own alerts and no conclusion of any kind, which
    is what its body says in as many words: passing alerts along untouched is
    the honest thing to do until something has actually looked at them.

    Lives beside ``TriageReport`` rather than in an adapter because it needs
    nothing but the incident. What replaces it will need a model and a tool
    call, and will arrive as an adapter behind the same one-argument callable
    the run already takes.

    Args:
        incident: The incident to report, with the alerts absorbed so far.

    Returns:
        A report naming the service and listing every alert on record for it.
    """
    return TriageReport(
        incident=incident,
        subject=_subject(incident),
        body=_body(incident),
    )


def _subject(incident: Incident) -> str:
    """Announce the incident in the one line every channel can carry."""
    return (
        f"[alert-triage] {_one_line(incident.service)}: "
        f"{_alert_count(len(incident.alerts))} awaiting triage"
    )


def _body(incident: Incident) -> str:
    """Say what fired, when, and where to look — and that nobody has looked."""
    lines = [
        f"{_alert_count(len(incident.alerts))} fired for service "
        f"{incident.service} since {incident.started_at.isoformat()}.",
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
    """Flatten anything a platform's tag might carry into a subject-safe fragment."""
    return " ".join(value.split())
