from datetime import UTC, datetime

import pytest

from alert_triage.domain.alert import Alert
from alert_triage.domain.findings import Findings
from alert_triage.domain.incident import Incident
from alert_triage.ports.investigator import Investigator, InvestigatorError

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


class _Investigator:
    """Everything the port asks of an implementation, and nothing more."""

    def investigate(self, incident: Incident) -> Findings:
        return Findings()


def _incident() -> Incident:
    return Incident(
        id="incident-1",
        service="checkout",
        alerts=(Alert(service="checkout", fired_at=NOON),),
    )


def test_an_implementation_needs_only_the_ports_own_vocabulary() -> None:
    assert isinstance(_Investigator(), Investigator)


def test_something_without_the_investigation_is_not_an_investigator() -> None:
    class _NotAnInvestigator:
        pass

    assert not isinstance(_NotAnInvestigator(), Investigator)


def test_the_failure_is_defined_beside_the_port() -> None:
    """'We could not look' and 'we looked and found nothing' are opposite news."""
    with pytest.raises(InvestigatorError):
        raise InvestigatorError("the platform was unreachable")


def test_an_investigation_is_asked_about_a_whole_incident() -> None:
    assert _Investigator().investigate(_incident()) == Findings()
