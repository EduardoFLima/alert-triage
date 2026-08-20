"""What an investigation came back with, in this project's own vocabulary.

A finding is an *observation* with the evidence behind it. It is deliberately
not a conclusion: there is nowhere here to put a root cause, a hypothesis, or a
confidence level, because nothing in this slice is entitled to state one. The
Diagnostician that will be entitled to one produces its own value from these.

Evidence is a log record the observability platform actually returned, never
text the investigation wrote. That distinction is enforced where findings are
built — an agent cites what it retrieved and the adapter reproduces the real
record — and it is the reason ``examples`` holds ``LogRecord`` values rather
than a string an agent could have invented.

A finding describes a pattern rather than reprinting it: ``occurrences`` says
how many times the pattern was seen, and ``examples`` carries a bounded handful
of the records themselves, so a service logging thousands of lines still
produces a report a human will read.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

MAX_EXAMPLES_PER_FINDING = 10
"""How many records a finding illustrates its pattern with.

A domain constant rather than a configured value: it is what keeps a finding
readable in an email, which is a property of reports rather than a knob an
operator tunes per team.
"""


class Signal(StrEnum):
    """The observability dimension a finding was drawn from.

    One member per specialist agent. Slice 7 adds the rest; a finding names its
    signal so that a report of several specialists' work stays legible without
    changing shape.
    """

    LOGS = "logs"


@dataclass(frozen=True)
class LogRecord:
    """One log line, as the observability platform reported it.

    Deliberately thin. What a human needs to recognise a line and find it again
    is when it happened, how bad the platform thought it was, what it said, and
    who emitted it — not the platform's full document with its every enrichment.

    Attributes:
        timestamp: When the line was logged.
        level: Severity as the platform labelled it.
        message: The line itself.
        service: Service that emitted it.
    """

    timestamp: datetime
    level: str
    message: str
    service: str

    def __post_init__(self) -> None:
        """Reject a record with nothing to say, which evidences nothing."""
        if not self.message.strip():
            raise ValueError("A log record without a message is not evidence")


@dataclass(frozen=True)
class Finding:
    """One thing an investigation noticed, with the records that show it.

    Attributes:
        signal: The observability dimension this was drawn from.
        observation: What was noticed, in the investigation's own words. This
            is its characterisation of the evidence, not the evidence itself:
            the records below are what a reader checks it against.
        occurrences: How many times the pattern was seen. Never fewer than the
            examples kept, which would be a record contradicting itself.
        examples: Records illustrating the pattern, oldest first, capped at
            ``MAX_EXAMPLES_PER_FINDING``. Never empty — a finding that shows
            nothing is an assertion.
    """

    signal: Signal
    observation: str
    occurrences: int
    examples: tuple[LogRecord, ...]

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

    Attributes:
        findings: What was found, in the order the investigation reported it.
    """

    findings: tuple[Finding, ...] = ()

    @property
    def anything_notable(self) -> bool:
        """Whether the investigation found anything worth a reader's attention."""
        return bool(self.findings)
