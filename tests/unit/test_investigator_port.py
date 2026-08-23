from datetime import UTC, datetime

import pytest

from alert_triage.domain.findings import Findings
from alert_triage.domain.investigation_target import InvestigationTarget
from alert_triage.domain.window import Window
from alert_triage.ports.investigator import Investigator, InvestigatorError

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


class _Investigator:
    """Everything the port asks of an implementation, and nothing more."""

    def investigate(self, target: InvestigationTarget) -> Findings:
        return Findings()


def _target() -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON),
        alert_count=2,
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


def test_an_investigation_is_asked_about_a_target_and_not_about_an_incident() -> None:
    """The port's vocabulary is a service, a window, and how much fired in it."""
    target = _target()

    assert (target.service, target.window.start, target.alert_count) == (
        "checkout",
        NOON,
        2,
    )
    assert _Investigator().investigate(target) == Findings()
