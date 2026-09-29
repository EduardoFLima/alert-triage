from typing import Protocol, runtime_checkable

from alert_triage.investigation.contract import Diagnosis, InvestigationTarget


class InvestigatorError(Exception):
    """Empty findings mean clean; this means nobody looked."""


@runtime_checkable
class Investigator(Protocol):
    def investigate(self, target: InvestigationTarget) -> Diagnosis: ...
