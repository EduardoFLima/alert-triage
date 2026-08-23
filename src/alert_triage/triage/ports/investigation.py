"""The Investigator port: the first-pass legwork, behind one question.

A caller hands over a target and receives findings. How many specialist agents
ran, which model reasoned, and which observability platform answered do not
cross this boundary — which is what lets slice 7 add three more specialists
without the run noticing, and what lets a complete run be exercised against a
substitute with no model and no network.

The target, not the incident, is the whole argument. What an investigation
needs is a service, a window, and how much fired in it; an incident is triage's
own aggregate and stays on triage's side of this line.

Synchronous by design, matching every other port. The adapter behind this is
asynchronous underneath and owns that internally; a component with no
concurrency to exploit should not push an event loop into the composition root.
"""

from typing import Protocol, runtime_checkable

from alert_triage.investigation.contract import (
    Findings,
    InvestigationTarget,
    InvestigatorError,
)

__all__ = ["Investigator", "InvestigatorError"]
"""``InvestigatorError`` is re-exposed because catching it is part of using this
port: a caller depends on the port and should not have to reach into the other
context's contract to name the failure the port documents."""


@runtime_checkable
class Investigator(Protocol):
    """An investigation of one target, in this project's vocabulary."""

    def investigate(self, target: InvestigationTarget) -> Findings:
        """Investigate one target and report what was found.

        Args:
            target: What to investigate: the service, the window to gather
                evidence around, and how many alerts are on record for it.

        Returns:
            What was found. Empty findings mean the investigation ran and found
            nothing notable, which is a success and worth reporting as one.

        Raises:
            InvestigatorError: The investigation could not be completed. Never
                signalled by returning empty findings.
        """
        ...
