"""The TriageLedger port: what the system remembers between runs.

Two questions cross this boundary — "which incidents are on record for this
service?" and "here is an incident's state, keep it" — and neither of them is
a decision. Continuation and the re-notify cooldown are domain rules in
``domain/triage.py``; a port that decided them would push the arithmetic into
every adapter and make the rule untestable without a database.

Retrieval offers only *open* incidents. Retained history is filtered out at
the boundary rather than skipped by the caller, so a record kept for a human
to consult cannot influence a decision by being forgotten about.

Synchronous by design, matching ``AlertSource``: an adapter makes ordinary
blocking calls, and nothing here has concurrency to exploit.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from alert_triage.domain.incident import Incident


class TriageLedgerError(Exception):
    """The ledger could not be read or written, so its answer must not be believed.

    Defined beside the port rather than in the adapter that raises it. This
    matters more here than anywhere else: a failed read that returned no
    incidents would be indistinguishable from "nothing has been reported yet",
    and would re-report every live incident as new.
    """


@runtime_checkable
class TriageLedger(Protocol):
    """The incidents on record, in this project's vocabulary."""

    def open_incidents(self, service: str, now: datetime) -> Sequence[Incident]:
        """Retrieve the still-open incidents on record for a service.

        Args:
            service: Service tag whose incidents are wanted.
            now: The instant to judge openness against, supplied rather than
                read from a clock so a run's decisions stay reproducible.

        Returns:
            The open incidents, each with the alerts absorbed into it. An
            empty result means nothing is on record, which is a success.

        Raises:
            TriageLedgerError: The incidents could not be retrieved. Never
                signalled by returning an empty or partial result.
        """
        ...

    def record(self, incident: Incident, now: datetime) -> None:
        """Record an incident's state as of this run.

        Args:
            incident: The incident to store, whether newly opened or
                continued.
            now: The instant this run is happening at.

        Raises:
            TriageLedgerError: The incident could not be recorded. Never
                signalled by returning quietly.
        """
        ...
