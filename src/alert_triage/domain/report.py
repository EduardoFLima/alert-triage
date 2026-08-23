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
from alert_triage.domain.findings import EvidenceItem, Finding, Findings
from alert_triage.domain.incident import Incident

NOT_INVESTIGATED = (
    "Investigation was attempted for these alerts and could not complete. This "
    "report lists what fired and nothing more."
)

NOTHING_NOTABLE = (
    "The logs around these alerts were searched and nothing notable was found."
)

EVIDENCE_INCOMPLETE = (
    "Part of the evidence this investigation asked for could not be gathered, so "
    "what follows was drawn from less than the platform holds. Read it as "
    "incomplete rather than as all there was to find."
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


def _build_pass_through_report(incident: Incident) -> TriageReport:
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


def build_report(incident: Incident, findings: Findings | None) -> TriageReport:
    """Build the report an incident has earned, given what was learned about it.

    The presence of findings is the whole decision. ``None`` means no
    investigation of this incident ever completed, which is the only case the
    pass-through report is for; empty findings mean one completed and found
    nothing, which is a result and reads as one. Why an investigation failed,
    and how many attempts it took to give up, are the run's business and never
    change what a report says.

    Args:
        incident: The incident to report.
        findings: What the investigation came back with, or ``None`` when none
            completed.

    Returns:
        The report to deliver.
    """
    if findings is None:
        return _build_pass_through_report(incident)
    return _build_investigated_report(incident, findings)


def _build_investigated_report(incident: Incident, findings: Findings) -> TriageReport:
    """Build the report for an incident an investigation actually looked at.

    States what was found and the records behind it, and still lists the alerts
    — a reader wants both the evidence and the thing that woke them up. Empty
    findings are reported as the result they are: the logs were searched and
    were clean, which is news rather than an empty section.

    Offers no hypothesis, root cause, or confidence level. Nothing in this
    slice produces one, and a report that implied otherwise would be the
    verdict this project deliberately does not give.

    Args:
        incident: The incident to report, with the alerts absorbed so far.
        findings: What the investigation came back with.

    Returns:
        A report naming the service, stating the findings with their evidence,
        and listing every alert on record.
    """
    return TriageReport(
        incident=incident,
        subject=_investigated_subject(incident, findings),
        body=_investigated_body(incident, findings),
    )


def _investigated_subject(incident: Incident, findings: Findings) -> str:
    """Announce the incident and whether looking at it turned anything up."""
    found = (
        f"{len(findings.findings)} finding"
        + ("" if len(findings.findings) == 1 else "s")
        if findings.anything_notable
        else "nothing notable"
    )
    return f"[alert-triage] {_one_line(incident.service)}: {found}"


def _investigated_body(incident: Incident, findings: Findings) -> str:
    """Lead with what was found, then the alerts that prompted looking."""
    lines = [
        f"{_alert_count(len(incident.alerts))} fired for service "
        f"{incident.service} since {incident.window.start.isoformat()}.",
        "",
        *_findings_lines(findings),
        "",
        "Alerts:",
        *(_alert_line(alert) for alert in incident.alerts),
    ]
    return "\n".join(lines)


def _findings_lines(findings: Findings) -> list[str]:
    """Every finding with its count and the evidence that shows it.

    Led by the incompleteness note where there is one: a reader deciding how
    much weight to put on what follows needs to know before they read it, not
    after.
    """
    lines = [] if findings.complete else [EVIDENCE_INCOMPLETE, ""]
    if not findings.anything_notable:
        return [*lines, NOTHING_NOTABLE]
    lines.append("What the investigation found:")
    for finding in findings.findings:
        lines.extend(("", *_finding_lines(finding)))
    return lines


def _finding_lines(finding: Finding) -> list[str]:
    """One finding: what was observed, how often, and the evidence for it."""
    occurrences = f"seen {finding.occurrences} time" + (
        "" if finding.occurrences == 1 else "s"
    )
    return [
        f"- [{finding.signal}] {finding.observation} ({occurrences})",
        *(f"    {_evidence_line(item)}" for item in finding.examples),
    ]


def _evidence_line(item: EvidenceItem) -> str:
    """One piece of evidence, reproduced as the platform reported it.

    An item with no instant is an aggregate — a graph, a map, a count over a
    window — and reads as one rather than as a line missing its timestamp.
    """
    if item.instant is None:
        return item.summary
    return f"{item.instant.isoformat()} {item.summary}"


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
    """Flatten anything a platform's tag might carry into a subject-safe fragment."""
    return " ".join(value.split())
