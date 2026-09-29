from collections.abc import Callable, Sequence

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

NOTHING_EXAMINED = (
    "No signal was examined around these alerts, so nothing notable could be found."
)

SERVICE_PAGE_LABEL = "Look at the service:"

FindingPage = Callable[[Finding], str | None]

NO_HYPOTHESIS = (
    "The investigation reached no hypothesis about these alerts. What it did "
    "examine is below."
)


CONFIDENCE_TEMPLATE = "Confidence in this reading: {level}."


def compose(
    narrative: str,
    findings: Findings,
    confidence: Confidence | None = None,
    page: FindingPage | None = None,
) -> str:
    weight = (
        []
        if confidence is None
        else [CONFIDENCE_TEMPLATE.format(level=confidence.value), ""]
    )
    return "\n".join([narrative.strip(), "", *weight, *evidence_lines(findings, page)])


def without_words(
    hypothesis: str | None,
    confidence: Confidence | None,
    findings: Findings,
    page: FindingPage | None = None,
) -> str:
    return "\n".join(
        [*_conclusion_lines(hypothesis, confidence), *evidence_lines(findings, page)]
    )


def headline_for(service: str, findings: Findings) -> str:
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
    if hypothesis is None:
        return [NO_HYPOTHESIS, ""]
    weight = "" if confidence is None else f" (confidence: {confidence.value})"
    return [f"What this looks like{weight}:", "", hypothesis.strip(), ""]


def evidence_lines(findings: Findings, page: FindingPage | None = None) -> list[str]:
    lines = [] if findings.complete else [EVIDENCE_INCOMPLETE, ""]
    if not findings.anything_notable:
        return [*lines, nothing_notable(findings.consulted)]
    lines.append("What the investigation found:")
    for finding in findings.findings:
        lines.extend(("", *_finding_lines(finding, page)))
    return lines


def nothing_notable(consulted: Sequence[Signal]) -> str:
    if not consulted:
        return NOTHING_EXAMINED
    return NOTHING_NOTABLE_TEMPLATE.format(signals=_listed(consulted))


def _listed(signals: Sequence[Signal]) -> str:
    named = [signal.value for signal in signals]
    if len(named) == 1:
        return named[0]
    return f"{', '.join(named[:-1])} and {named[-1]}"


def _finding_lines(finding: Finding, page: FindingPage | None) -> list[str]:
    occurrences = f"seen {finding.occurrences} time" + (
        "" if finding.occurrences == 1 else "s"
    )
    lines = [f"- [{finding.signal}] {finding.observation} ({occurrences})"]
    address = None if page is None else page(finding)
    if address is not None:
        lines.append(f"    {SERVICE_PAGE_LABEL} {address}")
    for item in finding.examples:
        lines.extend(f"    {line}" for line in _evidence_item_lines(item))
    return lines


def _evidence_item_lines(item: EvidenceItem) -> list[str]:
    """URLs stay on their own line so linkifiers never shorten or split them."""
    read = (
        item.summary
        if item.instant is None
        else f"{item.instant.isoformat()} {item.summary}"
    )
    return [read] if item.url is None else [read, item.url]
