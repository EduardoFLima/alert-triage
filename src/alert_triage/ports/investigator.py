"""The Investigator port: the first-pass legwork, behind one question.

A caller hands over an incident and receives findings. How many specialist
agents ran, which model reasoned, and which observability platform answered do
not cross this boundary — which is what lets slice 7 add three more specialists
without the run noticing, and what lets a complete run be exercised against a
substitute with no model and no network.

An incident is the whole argument. It already carries the service, the alerts,
and the window they span, so nothing has to be passed alongside it and nothing
has to be recomputed from it.

Synchronous by design, matching every other port. The adapter behind this is
asynchronous underneath and owns that internally; a component with no
concurrency to exploit should not push an event loop into the composition root.
"""

from typing import Protocol, runtime_checkable

from alert_triage.domain.findings import Findings
from alert_triage.domain.incident import Incident


class InvestigatorError(Exception):
    """An investigation could not be completed, so its silence proves nothing.

    Defined beside the port rather than in the adapter that raises it, and the
    distinction it draws is the important one in this slice: empty findings
    mean the platform answered and there was nothing notable, while this means
    nobody looked. Reporting the first as the second would tell a team its logs
    are clean on the strength of a failed request.
    """


@runtime_checkable
class Investigator(Protocol):
    """An investigation of one incident, in this project's vocabulary."""

    def investigate(self, incident: Incident) -> Findings:
        """Investigate one incident and report what was found.

        Args:
            incident: The incident to investigate, with the alerts absorbed so
                far and the window they span.

        Returns:
            What was found. Empty findings mean the investigation ran and found
            nothing notable, which is a success and worth reporting as one.

        Raises:
            InvestigatorError: The investigation could not be completed. Never
                signalled by returning empty findings.
        """
        ...
