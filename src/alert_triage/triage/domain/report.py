"""What one incident is worth telling a team, and how that is worded.

Deciding what to say about an incident belongs here, beside the incident:
whether an investigation ran, what it found, and which alerts to list are
triage's own facts. Delivering what comes out is the notification context's
work, and ``TriageReport`` is the contract it publishes for the purpose.
"""

from collections.abc import Sequence

from alert_triage.investigation.contract import EvidenceItem, Finding, Findings, Signal
from alert_triage.notification.contract import TriageReport
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.incident import Incident

NOT_INVESTIGATED = (
    "Investigation was attempted for these alerts and could not complete. This "
    "report lists what fired and nothing more."
)

NOTHING_NOTABLE_TEMPLATE = (
    "The {signals} around these alerts were examined and nothing notable was found."
)
"""What a clean investigation says, once it says what it covered.

Built from the signals the investigation examined rather than fixed, because
"nothing notable" is only interpretable against a scope: a reader told the logs
were clean draws a different conclusion from one told that the logs, the golden
signals, the traces and the infrastructure were all clean. Whoever calls this
states the scope, so a crew that grows widens the sentence and a report never
claims a signal nobody looked at.
"""

NOTHING_EXAMINED = (
    "No signal was examined around these alerts, so nothing notable could be found."
)
"""What is said when an investigation completed having looked at nothing.

Only reachable from a deployment configured with no specialists at all. It is
still worded rather than left to the template, because a sentence naming an
empty list of signals is how a report starts lying about its scope.
"""

EVIDENCE_INCOMPLETE = (
    "Part of the evidence this investigation asked for could not be gathered, so "
    "what follows was drawn from less than the platform holds. Read it as "
    "incomplete rather than as all there was to find."
)

NO_TITLE = "(no title reported)"
NO_LINK = "(no link reported)"


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
        incident_id=incident.id,
        service=incident.service,
        subject=_subject(incident),
        body=_body(incident),
    )


def build_report(
    incident: Incident,
    findings: Findings | None,
    *,
    examined: Sequence[Signal],
) -> TriageReport:
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
        examined: The signals the investigation looks at, so that what it found
            can be read against what it covered. Stated by the caller because
            which specialists a deployment runs is not triage's to know.

    Returns:
        The report to deliver.
    """
    if findings is None:
        return _build_pass_through_report(incident)
    return _build_investigated_report(incident, findings, examined)


def _build_investigated_report(
    incident: Incident, findings: Findings, examined: Sequence[Signal]
) -> TriageReport:
    """Build the report for an incident an investigation actually looked at.

    States what was found and the records behind it, and still lists the alerts
    — a reader wants both the evidence and the thing that woke them up. Empty
    findings are reported as the result they are: these signals were examined
    and were clean, which is news rather than an empty section.

    Offers no hypothesis, root cause, or confidence level. Nothing in this
    slice produces one, and a report that implied otherwise would be the
    verdict this project deliberately does not give.

    Args:
        incident: The incident to report, with the alerts absorbed so far.
        findings: What the investigation came back with.
        examined: The signals the investigation looks at.

    Returns:
        A report naming the service, stating the findings with their evidence,
        and listing every alert on record.
    """
    return TriageReport(
        incident_id=incident.id,
        service=incident.service,
        subject=_investigated_subject(incident, findings),
        body=_investigated_body(incident, findings, examined),
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


def _investigated_body(
    incident: Incident, findings: Findings, examined: Sequence[Signal]
) -> str:
    """Lead with what was found, then the alerts that prompted looking."""
    lines = [
        f"{_alert_count(len(incident.alerts))} fired for service "
        f"{incident.service} since {incident.window.start.isoformat()}.",
        "",
        *_findings_lines(findings, examined),
        "",
        "Alerts:",
        *(_alert_line(alert) for alert in incident.alerts),
    ]
    return "\n".join(lines)


def _findings_lines(findings: Findings, examined: Sequence[Signal]) -> list[str]:
    """Every finding with its count and the evidence that shows it.

    Led by the incompleteness note where there is one: a reader deciding how
    much weight to put on what follows needs to know before they read it, not
    after.
    """
    lines = [] if findings.complete else [EVIDENCE_INCOMPLETE, ""]
    if not findings.anything_notable:
        return [*lines, nothing_notable(examined)]
    lines.append("What the investigation found:")
    for finding in findings.findings:
        lines.extend(("", *_finding_lines(finding)))
    return lines


def nothing_notable(examined: Sequence[Signal]) -> str:
    """Say that nothing was found, and what was looked at to find nothing in.

    Args:
        examined: The signals the investigation looks at.

    Returns:
        The sentence a clean investigation is reported with.
    """
    if not examined:
        return NOTHING_EXAMINED
    return NOTHING_NOTABLE_TEMPLATE.format(signals=_listed(examined))


def _listed(signals: Sequence[Signal]) -> str:
    """Name the signals in the one form a sentence can carry."""
    named = [signal.value for signal in signals]
    if len(named) == 1:
        return named[0]
    return f"{', '.join(named[:-1])} and {named[-1]}"


def _finding_lines(finding: Finding) -> list[str]:
    """One finding: what was observed, how often, and the evidence for it."""
    occurrences = f"seen {finding.occurrences} time" + (
        "" if finding.occurrences == 1 else "s"
    )
    lines = [f"- [{finding.signal}] {finding.observation} ({occurrences})"]
    for item in finding.examples:
        lines.extend(f"    {line}" for line in _evidence_lines(item))
    return lines


def _evidence_lines(item: EvidenceItem) -> list[str]:
    """One piece of evidence, reproduced as the platform reported it.

    An item with no instant is an aggregate — a graph, a map, a count over a
    window — and reads as one rather than as a line missing its timestamp.

    An address the platform gave for it stands on a line of its own, below what
    was retrieved rather than inside it. A channel that turns addresses into
    links finds a whole one, and one that does not shows a reader something
    they can copy — and neither ends up inside the text a summary is shortened
    within, which is a link leading somewhere the evidence is not.
    """
    read = (
        item.summary
        if item.instant is None
        else f"{item.instant.isoformat()} {item.summary}"
    )
    return [read] if item.url is None else [read, item.url]


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
