"""The AlertSource port: where the alerts to triage come from.

A caller asks one question — "which in-scope alerts have fired since this
instant?" — and receives domain ``Alert`` values. Which observability platform
answered, and in what wire format, does not cross this boundary: that
translation is an adapter's whole job, and keeping it there is what lets a
second platform be added without the pipeline noticing.

Synchronous by design. An adapter makes ordinary blocking calls, and a
component with no concurrency to exploit should not push an event loop into
the composition root. An adapter that later needs concurrency owns it
internally without reshaping the port.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from alert_triage.domain.alert import Alert


class AlertSourceError(Exception):
    """Alerts could not be retrieved, so the caller must not assume a quiet period.

    Defined beside the port rather than in the adapter that raises it: there is
    exactly one error type to catch, and a caller distinguishes "nothing fired"
    from "the fetch failed" without importing anything platform-specific.
    """


@runtime_checkable
class AlertSource(Protocol):
    """Recent in-scope alerts, in this project's vocabulary."""

    def fetch_since(self, since: datetime) -> Sequence[Alert]:
        """Fetch the in-scope alerts that fired at or after ``since``.

        Args:
            since: Instant the caller wants alerts from. Timezone-aware.

        Returns:
            The matching alerts, complete — every page of them. An empty
            result means nothing fired, which is a success.

        Raises:
            AlertSourceError: The alerts could not be retrieved. Never
                signalled by returning an empty or partial result.
        """
        ...
