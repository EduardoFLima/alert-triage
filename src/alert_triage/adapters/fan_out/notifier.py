"""Delivering one report to every configured channel.

The partial-failure rule lives here rather than in a caller's loop, which is
what makes it unit-testable without a pipeline around it — and what lets a
caller inject one ``Notifier`` and never learn how many channels sit behind it.

The rule itself is downstream-driven: slice 5 records an incident as reported
only when delivery returned, and "the team was told" is true as soon as one
channel got through. Raising on any single failure would let a broken relay
stop the cooldown from ever starting, and the incident would be re-reported to
the working channel every run — the alert fatigue this project exists to
reduce.
"""

import logging
from collections.abc import Sequence

from alert_triage.domain.report import TriageReport
from alert_triage.ports.notifier import Notifier, NotifierError

_log = logging.getLogger(__name__)


class FanOutNotifier:
    """A ``Notifier`` that delivers to several channels and survives some of them.

    Deliberately a ``Notifier`` itself: a single-channel deployment is then not
    a special case, and nothing downstream is shaped by how many channels a
    deployment happens to have.
    """

    def __init__(self, channels: Sequence[Notifier]) -> None:
        """Bind the fan-out to the channels a deployment configured.

        Args:
            channels: The channels to deliver through, in the order they are
                attempted.

        Raises:
            ValueError: No channel was supplied. A notifier that can tell
                nobody anything is a mistake worth finding at startup rather
                than when the first report is due.
        """
        if not channels:
            raise ValueError(
                "A fan-out notifier needs at least one channel: a report has to "
                "reach somebody"
            )
        self._channels = tuple(channels)

    @property
    def channels(self) -> tuple[Notifier, ...]:
        """The channels a report is delivered through, in the order attempted."""
        return self._channels

    def deliver(self, report: TriageReport) -> None:
        """Deliver the report to every channel, and fail only if none accepted it.

        Each channel is attempted exactly once. A failure is not retried here:
        a run that delivered nothing does not record the incident as reported,
        so the next run produces the report again — the ledger is the retry
        mechanism, and it is durable across processes in a way an in-run loop
        is not.

        Raises:
            NotifierError: Every channel failed, so the report reached nobody.
                The failure carries each channel's own reason.
        """
        failures = [
            failure
            for channel in self._channels
            if (failure := self._attempt(channel, report)) is not None
        ]
        if len(failures) < len(self._channels):
            self._log_partial(failures, report)
            return
        raise NotifierError(
            f"The report for incident {report.incident_id!r} reached no channel: "
            + "; ".join(failures)
        )

    def _attempt(self, channel: Notifier, report: TriageReport) -> str | None:
        """Attempt one channel, answering why it failed, or ``None`` if it did not.

        Every exception is caught, not only ``NotifierError``: a channel that
        breaks its own contract is still a channel that failed, and it must not
        take the ones after it down with it.
        """
        try:
            channel.deliver(report)
        except Exception as error:
            return f"{_name(channel)}: {error}"
        return None

    def _log_partial(self, failures: Sequence[str], report: TriageReport) -> None:
        """Surface the channels that failed while another got through.

        Delivery succeeded, so nothing is raised — but a team whose email has
        been broken for a week learns nothing from the Teams reports that keep
        arriving, and this is the only place that knows.
        """
        for failure in failures:
            _log.warning(
                "Report for incident %s was not delivered to one channel (%s)",
                report.incident_id,
                failure,
            )


def _name(channel: Notifier) -> str:
    """Name a channel by its type, which is what an operator recognises it as."""
    return type(channel).__name__
