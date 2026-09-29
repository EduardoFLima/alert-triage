import logging
from collections.abc import Sequence

from alert_triage.notification.contract import TriageReport
from alert_triage.notification.ports.notifier import Notifier, NotifierError
from alert_triage.shared import journal

_log = logging.getLogger(__name__)


class FanOutNotifier:
    def __init__(self, channels: Sequence[Notifier]) -> None:
        if not channels:
            raise ValueError(
                "A fan-out notifier needs at least one channel: a report has to "
                "reach somebody"
            )
        self._channels = tuple(channels)

    @property
    def channels(self) -> tuple[Notifier, ...]:
        return self._channels

    def deliver(self, report: TriageReport) -> None:
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
        try:
            channel.deliver(report)
        # One broken channel must not stop the others from receiving the report.
        except Exception as error:
            return f"{_name(channel)}: {error}"
        return None

    def _log_partial(self, failures: Sequence[str], report: TriageReport) -> None:
        for failure in failures:
            _log.warning(
                journal.event(
                    "a channel did not take the report",
                    incident=report.incident_id,
                    service=report.service,
                    detail=failure,
                )
            )


def _name(channel: Notifier) -> str:
    return type(channel).__name__
