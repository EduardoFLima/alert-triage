from typing import Protocol, runtime_checkable

from alert_triage.notification.contract import TriageReport


class NotifierError(Exception):
    pass


@runtime_checkable
class Notifier(Protocol):
    def deliver(self, report: TriageReport) -> None: ...
