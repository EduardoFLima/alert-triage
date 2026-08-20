"""The ObservabilityPlatform port: where a specialist agent gets its evidence.

Deliberately separate from ``AlertSource``, which they are easy to confuse.
Ingestion asks one fixed question on a schedule — "what fired since this
instant?" — and wants a typed answer. This port is what an *investigation*
reaches through: a specialist agent decides at runtime what it wants to know
about a service over a window, and asks.

The methods here are the whole vocabulary an agent has. That is the point: a
specialist is written against logs, traces, and metrics as this project
understands them, never against one platform's tool names or query dialect, so
substituting the platform behind this boundary leaves every agent unchanged.
Widening what an agent may ask for is a deliberate act — a method added here —
rather than a side effect of a vendor adding a tool.

Synchronous by design, matching every other port: an adapter makes ordinary
blocking calls, and an adapter that needs concurrency owns it internally
without reshaping the boundary.
"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from alert_triage.domain.findings import LogRecord
from alert_triage.domain.window import Window


class ObservabilityPlatformError(Exception):
    """Evidence could not be retrieved, so its absence must not be read as silence.

    Defined beside the port rather than in the adapter that raises it: an
    investigation tells "the service logged nothing" from "the search failed"
    without importing anything platform-specific, and those are opposite
    findings.
    """


@runtime_checkable
class ObservabilityPlatform(Protocol):
    """Observability evidence, in this project's vocabulary."""

    def search_logs(
        self, service: str, window: Window, query: str
    ) -> Sequence[LogRecord]:
        """Search a service's logs over a window.

        Args:
            service: Service tag whose logs are wanted.
            window: The period to search over.
            query: What to look for, in the caller's own terms. Translating it
                into a platform's query dialect is the adapter's work.

        Returns:
            The matching records, oldest first. An empty result means the
            service logged nothing matching, which is a success and a finding
            in its own right.

        Raises:
            ObservabilityPlatformError: The search could not be performed.
                Never signalled by returning an empty or partial result.
        """
        ...

    def count_logs(self, service: str, window: Window, query: str) -> int:
        """Count a service's matching log records over a window.

        Deliberately its own capability rather than something a caller derives
        from ``search_logs``. A search returns a page of records to read; this
        answers "how many are there", which is the number a finding reports and
        which no sample of records can establish.

        It exists so that "seen 400 times" is something the platform said
        rather than something the investigation counted, which is the
        difference between evidence and arithmetic nobody checked.

        Args:
            service: Service tag whose logs are counted.
            window: The period to count over.
            query: What to count, in the caller's own terms.

        Returns:
            How many records matched. Zero is a success.

        Raises:
            ObservabilityPlatformError: The count could not be performed. Never
                signalled by returning zero.
        """
        ...
