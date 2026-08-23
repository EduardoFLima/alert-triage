"""What an investigation is asked about: a service, a stretch of time, a volume.

An investigation never learns what an incident is. It is told which service to
look at, which window to gather evidence around, and how much fired in it —
which is everything the specialists actually read off an incident today, and a
record someone writing a specialist for another platform can understand without
this project's aggregate in front of them.

Translating an incident into a target is triage's work, done where an incident
is already in hand. What comes back is ``Findings``, which names no incident
either.
"""

from dataclasses import dataclass

from alert_triage.domain.window import Window


@dataclass(frozen=True)
class InvestigationTarget:
    """One investigation's subject, stated without reference to an incident.

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
