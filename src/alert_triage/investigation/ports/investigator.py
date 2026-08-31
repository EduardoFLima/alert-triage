"""The Investigator port: the first-pass legwork, behind one question.

A caller hands over a target and receives a diagnosis: what was found, the
signals it was found in, and what the investigation concludes from them. Which
specialists exist, which model reasoned, in what order they were reached, and
which observability platform answered do not cross this boundary — which is
what lets the crew grow and the routing change without the run noticing, and
what lets a complete run be exercised against a substitute with no model and no
network.

The one thing about the crew that does cross is which signals were consulted,
and it has to: a report states its own scope, and a scope it took on trust from
the composition root would say what the deployment declared rather than what
this investigation actually did.

The target, not the incident, is the whole argument. What an investigation
needs is a service, a window, and how much fired in it; an incident is triage's
own aggregate and stays on triage's side of this line.

Declared here rather than beside the caller because this is the way *into* this
context, and the thing implementing it is this context's own adapter. Triage
never calls through it — the pipeline in ``app`` does, and a composition root
is entitled to name both ends. Filing it under triage would have put the one
port in the tree whose owning context sits on neither end of it.

Synchronous by design, matching every other port. The adapter behind this is
asynchronous underneath and owns that internally; a component with no
concurrency to exploit should not push an event loop into the composition root.
"""

from typing import Protocol, runtime_checkable

from alert_triage.investigation.contract import Diagnosis, InvestigationTarget


class InvestigatorError(Exception):
    """An investigation could not be completed, so its silence proves nothing.

    Defined beside the port rather than in the adapter that raises it, and the
    distinction it draws is the important one: empty findings mean the platform
    answered and there was nothing notable, while this means nobody looked.
    Reporting the first as the second would tell a team its logs are clean on
    the strength of a failed request.
    """


@runtime_checkable
class Investigator(Protocol):
    """An investigation of one target, in this project's vocabulary."""

    def investigate(self, target: InvestigationTarget) -> Diagnosis:
        """Investigate one target and report what was found and concluded.

        Args:
            target: What to investigate: the service, the window to gather
                evidence around, and how many alerts are on record for it.

        Returns:
            What was found, what was consulted to find it, and what the
            investigation concludes. Empty findings mean the investigation ran
            and found nothing notable, which is a success and worth reporting as
            one; no hypothesis means it could not conclude, which is also an
            answer.

        Raises:
            InvestigatorError: The investigation could not be completed. Never
                signalled by returning empty findings.
        """
        ...
