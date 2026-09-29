from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from alert_triage.shared.window import Window

# A single alert spans an instant; platform queries need a period.
MINIMUM_EVIDENCE_SPAN = timedelta(minutes=5)
# Keeps emailed findings readable.
MAX_EXAMPLES_PER_FINDING = 10


_CRITICAL = "critical — treat this incident with more urgency"
_ORDINARY = "not declared critical"
_NO_ENVIRONMENT = "none given — scope by the service alone"


@dataclass(frozen=True)
class InvestigationTarget:
    """Flat input record so investigation never needs triage's Incident."""

    service: str
    window: Window
    alert_count: int
    critical: bool = False
    env: str | None = None

    def __post_init__(self) -> None:
        span = self.window.end - self.window.start
        if span >= MINIMUM_EVIDENCE_SPAN:
            return
        margin = (MINIMUM_EVIDENCE_SPAN - span) / 2
        object.__setattr__(
            self,
            "window",
            Window(start=self.window.start - margin, end=self.window.end + margin),
        )

    def describe(self) -> str:
        """State criticality and environment either way so silence is not ambiguous."""
        return (
            f"Service: {self.service}\n"
            f"Environment: {self.env or _NO_ENVIRONMENT}\n"
            f"Service criticality: {_CRITICAL if self.critical else _ORDINARY}\n"
            f"Window start: {self.window.start.isoformat()}\n"
            f"Window end: {self.window.end.isoformat()}\n"
            f"Alerts in this incident: {self.alert_count}"
        )


class Signal(StrEnum):
    LOGS = "logs"
    APM = "apm"
    TRACE = "trace"
    INFRASTRUCTURE = "infrastructure"


# pydantic copies this docstring into the output schema the specialists answer
# in, so it is prompt text: change it only with the live suite.
class Section(StrEnum):
    """Which part of the service a finding concerns, for a reader landing on it.

    The one part of an address the reasoning is allowed to contribute, and a
    closed set for the reason ``Confidence`` is one: a member can be checked
    and a sentence cannot. The system composes the address around it — host,
    path, service, window — and a wrong member lands a reader on the right
    service looking at the wrong part of it, which is recoverable in a way a
    written address is not.

    Named for what a reader goes to look at rather than for any platform's
    page, so a second platform's adapter maps these to its own layout.
    """

    ERRORS = "errors"
    DEPLOYMENTS = "deployments"
    DEPENDENCIES = "dependencies"
    INFRASTRUCTURE = "infrastructure"
    TRACES = "traces"
    LOGS = "logs"


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    instant: datetime | None
    summary: str
    payload: Any
    # None means the platform offered no address, not that one failed to build.
    url: str | None = None

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError(
                "Evidence without a summary is unreadable, so it is not evidence"
            )


@dataclass(frozen=True)
class Finding:
    signal: Signal
    observation: str
    occurrences: int
    examples: tuple[EvidenceItem, ...]
    section: Section | None = None

    def __post_init__(self) -> None:
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
    """Empty, incomplete, and unconsulted are separate pieces of news."""

    findings: tuple[Finding, ...] = ()
    retrieval_failures: tuple[str, ...] = ()
    consulted: tuple[Signal, ...] = ()

    @property
    def anything_notable(self) -> bool:
        return bool(self.findings)

    @property
    def complete(self) -> bool:
        return not self.retrieval_failures


class Confidence(StrEnum):
    """Closed set so confidence is comparable."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Diagnosis:
    """A conclusion travels only with the findings it was drawn from."""

    headline: str
    account: str
    hypothesis: str | None
    confidence: Confidence | None
    findings: Findings

    def __post_init__(self) -> None:
        if not self.headline.strip():
            raise ValueError("A diagnosis needs a headline to announce it")
        if "\n" in self.headline or "\r" in self.headline:
            raise ValueError(
                "A diagnosis headline is a single line: put the detail in the account"
            )
        if not self.findings.findings:
            object.__setattr__(self, "hypothesis", None)
            object.__setattr__(self, "confidence", None)
        if self.hypothesis is None:
            object.__setattr__(self, "confidence", None)
