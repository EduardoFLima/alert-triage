"""The account a reader is given: prose over evidence reproduced as it was retrieved.

An agent words the report, and this renders what the wording is checked against.
The split is the evidence discipline surviving its last hop. A model asked to
write a report will write a log line into it, plausibly and unverifiably, and
nothing downstream could tell. So the writer characterises and this reproduces:
what a reader sees beneath the prose is what the platform actually returned.

Everything here is derived from the contract's own values and the standard
library. No agent framework, no platform, no vendor: rendering an account is
this context's, and a deployment swapping either keeps it.
"""

from collections.abc import Sequence

from alert_triage.investigation.contract import (
    Confidence,
    EvidenceItem,
    Finding,
    Findings,
    Signal,
)

EVIDENCE_INCOMPLETE = (
    "Part of the evidence this investigation asked for could not be gathered, so "
    "what follows was drawn from less than the platform holds. Read it as "
    "incomplete rather than as all there was to find."
)

NOTHING_NOTABLE_TEMPLATE = (
    "The {signals} around these alerts were examined and nothing notable was found."
)
"""What a clean investigation says, once it says what it covered.

Built from the signals actually consulted rather than from the crew declared: a
reader told the logs were clean draws a different conclusion from one told the
logs, the golden signals, the traces and the infrastructure were all clean, and
a specialist the manager chose not to call has told us nothing about its signal.
"""

NOTHING_EXAMINED = (
    "No signal was examined around these alerts, so nothing notable could be found."
)
"""What is said when an investigation completed having consulted nobody.

Worded rather than left to the template, because a sentence naming an empty list
of signals is how a report starts lying about its scope.
"""

NO_HYPOTHESIS = (
    "The investigation reached no hypothesis about these alerts. What it did "
    "examine is below."
)


def without_words(
    hypothesis: str | None, confidence: Confidence | None, findings: Findings
) -> str:
    """The account this project composes when no agent worded one.

    Not emergency code kept warm: it is the same renderer with nothing written
    above it. A report is worth more than its wording, and everything it carries
    was gathered before any of it was worded.

    Args:
        hypothesis: What the investigation concluded, if anything.
        confidence: How much weight it put on that.
        findings: What the investigation found.

    Returns:
        The account, stating the conclusion plainly and then showing its basis.
    """
    return "\n".join(
        [*_conclusion_lines(hypothesis, confidence), *evidence_lines(findings)]
    )


def headline_for(service: str, findings: Findings) -> str:
    """The one line to announce this investigation when no agent wrote one."""
    found = (
        f"{len(findings.findings)} finding"
        + ("" if len(findings.findings) == 1 else "s")
        if findings.anything_notable
        else "nothing notable"
    )
    return f"{' '.join(service.split())}: {found}"


def _conclusion_lines(
    hypothesis: str | None, confidence: Confidence | None
) -> list[str]:
    """State the conclusion, or state plainly that there was none."""
    if hypothesis is None:
        return [NO_HYPOTHESIS, ""]
    weight = "" if confidence is None else f" (confidence: {confidence.value})"
    return [f"What this looks like{weight}:", "", hypothesis.strip(), ""]


def evidence_lines(findings: Findings) -> list[str]:
    """Every finding with its count and the evidence that shows it.

    Led by the incompleteness note where there is one: a reader deciding how
    much weight to put on what follows needs to know before they read it, not
    after.
    """
    lines = [] if findings.complete else [EVIDENCE_INCOMPLETE, ""]
    if not findings.anything_notable:
        return [*lines, nothing_notable(findings.consulted)]
    lines.append("What the investigation found:")
    for finding in findings.findings:
        lines.extend(("", *_finding_lines(finding)))
    return lines


def nothing_notable(consulted: Sequence[Signal]) -> str:
    """Say that nothing was found, and what was looked at to find nothing in.

    Args:
        consulted: The signals this investigation actually asked about.

    Returns:
        The sentence a clean investigation is reported with.
    """
    if not consulted:
        return NOTHING_EXAMINED
    return NOTHING_NOTABLE_TEMPLATE.format(signals=_listed(consulted))


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
        lines.extend(f"    {line}" for line in _evidence_item_lines(item))
    return lines


def _evidence_item_lines(item: EvidenceItem) -> list[str]:
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
