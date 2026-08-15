"""The Notifier port: how a triage report leaves the process.

One question crosses this boundary — "deliver this report" — and the answer is
either that it was delivered or an exception. There is no status value to
inspect, because a caller has exactly one decision to make on the outcome:
slice 5 records an incident as reported only when delivery returned, so a
delivery that quietly did nothing would start a cooldown on a report nobody
received.

What a channel does with a report — a MIME message, a card, an HTTP POST — is
the adapter's own business, and so is the shape of the destination. A fan-out
across several channels satisfies this same port, so a caller never learns how
many channels sit behind it.

Synchronous by design, matching ``AlertSource`` and ``TriageLedger``: an
adapter makes ordinary blocking calls, and nothing here has concurrency to
exploit.
"""

from typing import Protocol, runtime_checkable

from alert_triage.domain.report import TriageReport


class NotifierError(Exception):
    """A report was not delivered, so the caller must not treat it as reported.

    Defined beside the port rather than in the adapter that raises it: a caller
    tells "the team was told" from "the team was not told" without knowing
    which channel was involved or importing anything specific to it.
    """


@runtime_checkable
class Notifier(Protocol):
    """A destination a triage report can be delivered to."""

    def deliver(self, report: TriageReport) -> None:
        """Deliver one report to this notifier's destination.

        Args:
            report: The report to deliver. A channel renders it into the shape
                its own medium expects and carries the body unchanged.

        Raises:
            NotifierError: The report was not delivered — the destination was
                unreachable, or reached and refused it. Never signalled by
                returning quietly.
        """
        ...
