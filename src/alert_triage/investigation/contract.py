"""What investigation publishes: what it can be asked, and what it answers with.

Everything crossing into or out of this context is here and nowhere else. A
caller states a target — a service, a window, a volume — and receives findings.
It learns no specialist, no agent framework, and no observability platform, and
this context learns nothing about incidents in return.

A finding is an *observation* with the evidence behind it. It is deliberately
not a conclusion: there is nowhere here to put a root cause, a hypothesis, or a
confidence level, because nothing in this slice is entitled to state one. The
Diagnostician that will be entitled to one produces its own value from these.

Evidence is something the observability platform actually returned, never text
the investigation wrote. That distinction is enforced where findings are built
— an agent cites what it retrieved and the adapter reproduces the real item —
and it is the reason ``examples`` holds ``EvidenceItem`` values rather than a
string an agent could have invented. One type covers every tool: a specialist
reaching a new one needs no new value here, which is what keeps adding
specialists cheap.

A finding describes a pattern rather than reprinting it: ``occurrences`` says
how many times the pattern was seen, and ``examples`` carries a bounded handful
of the evidence itself, so a service logging thousands of lines still produces
a report a human will read.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from alert_triage.shared.window import Window

MAX_EXAMPLES_PER_FINDING = 10
"""How many pieces of evidence a finding illustrates its pattern with.

A domain constant rather than a configured value: it is what keeps a finding
readable in an email, which is a property of reports rather than a knob an
operator tunes per team.
"""


@dataclass(frozen=True)
class InvestigationTarget:
    """One investigation's subject, stated without reference to an incident.

    A four-field record rather than the caller's aggregate: someone writing a
    specialist for another platform reads this and needs nothing else, and this
    context never learns what an incident is. Translating one into a target is
    the caller's work, done where an incident is already in hand.

    Attributes:
        service: The service to investigate.
        window: The stretch of time to gather evidence around. Spans the
            alerts rather than the run that fetched them, so evidence is
            gathered around the problem.
        alert_count: How many alerts are on record for it. Volume is context a
            specialist weighs; which alerts they were is not its business.
    """

    service: str
    window: Window
    alert_count: int

    def describe(self) -> str:
        """State the target to a specialist, in terms any of them can use."""
        return (
            f"Service: {self.service}\n"
            f"Window start: {self.window.start.isoformat()}\n"
            f"Window end: {self.window.end.isoformat()}\n"
            f"Alerts in this incident: {self.alert_count}"
        )


class Signal(StrEnum):
    """The observability dimension a finding was drawn from.

    One member per specialist. A finding names its signal so that a report of
    several specialists' work stays legible without changing shape.
    """

    LOGS = "logs"
    APM = "apm"
    TRACE = "trace"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class EvidenceItem:
    """One thing the observability platform returned, in a shape anything can render.

    One type for every tool, deliberately. A per-tool value pays for itself only
    where the tool is known in advance, and a specialist discovers its tools at
    runtime: what a report needs is a line a human can read and the instant it
    concerns, and what an engineer needs beyond that is the payload itself,
    which travels along untouched.

    Attributes:
        id: What this item is cited by. Its grain is the retrieval it came from
            and its position within it, so an aggregate with no discrete items
            is still citable as a whole.
        instant: When it happened, where the payload said. ``None`` for an item
            that concerns a period rather than a moment.
        summary: The line a human reads to recognise this item.
        payload: What the platform actually returned, verbatim.
        url: Where a human opens this item on the platform. Derived from what
            was retrieved, never written by the investigation: an invented
            address cannot be checked the way an invented identifier can, and
            a reader will follow it. ``None`` where the platform offers no way
            to address the item, which is a complete answer rather than a
            failure.
    """

    id: str
    instant: datetime | None
    summary: str
    payload: Any
    url: str | None = None

    def __post_init__(self) -> None:
        """Reject an item nobody could read, which evidences nothing."""
        if not self.summary.strip():
            raise ValueError(
                "Evidence without a summary is unreadable, so it is not evidence"
            )


@dataclass(frozen=True)
class Finding:
    """One thing an investigation noticed, with the evidence that shows it.

    Attributes:
        signal: The observability dimension this was drawn from.
        observation: What was noticed, in the investigation's own words. This
            is its characterisation of the evidence, not the evidence itself:
            the items below are what a reader checks it against.
        occurrences: How many times the pattern was seen. Never fewer than the
            examples kept, which would be a record contradicting itself.
        examples: Evidence illustrating the pattern, oldest first, capped at
            ``MAX_EXAMPLES_PER_FINDING``. Never empty — a finding that shows
            nothing is an assertion.
    """

    signal: Signal
    observation: str
    occurrences: int
    examples: tuple[EvidenceItem, ...]

    def __post_init__(self) -> None:
        """Reject a finding that asserts more than it can show."""
        if not self.observation.strip():
            raise ValueError("A finding needs an observation to be about something")
        if not self.examples:
            raise ValueError(
                "A finding needs at least one example: evidence is what "
                "separates it from an assertion"
            )
        if self.occurrences < len(self.examples):
            raise ValueError(
                "A finding cannot have fewer occurrences than the examples it carries"
            )
        object.__setattr__(
            self, "examples", tuple(self.examples[:MAX_EXAMPLES_PER_FINDING])
        )


@dataclass(frozen=True)
class Findings:
    """Everything one investigation came back with.

    Empty is a legitimate, successful result: the platform answered and there
    was nothing worth reporting. That is deliberately not how failure is
    expressed — an investigation that could not run raises instead, so "we
    looked and the logs are clean" can never be mistaken for "we could not
    look", which are opposite pieces of news.

    Empty findings and incomplete evidence are different facts, and the second
    is why ``retrieval_failures`` exists: an investigation that could not see
    part of what it asked for still has something to say about the rest, and a
    reader must be able to tell that account from one drawn on everything.

    Attributes:
        findings: What was found, in the order the investigation reported it.
        retrieval_failures: Why each retrieval that failed did. Empty means
            everything the investigation asked for came back.
    """

    findings: tuple[Finding, ...] = ()
    retrieval_failures: tuple[str, ...] = ()

    @property
    def anything_notable(self) -> bool:
        """Whether the investigation found anything worth a reader's attention."""
        return bool(self.findings)

    @property
    def complete(self) -> bool:
        """Whether every retrieval the investigation asked for came back."""
        return not self.retrieval_failures
