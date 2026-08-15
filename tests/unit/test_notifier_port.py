import inspect
from dataclasses import dataclass, field
from datetime import UTC, datetime

from alert_triage.domain.alert import Alert
from alert_triage.domain.incident import Incident
from alert_triage.domain.report import TriageReport
from alert_triage.ports.notifier import Notifier, NotifierError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


@dataclass
class InMemoryNotifier:
    """What a test double for the port looks like: reports, no destination."""

    delivered: list[TriageReport] = field(default_factory=list)

    def deliver(self, report: TriageReport) -> None:
        """Accept the report, as a destination that is always reachable would."""
        self.delivered.append(report)


def _report() -> TriageReport:
    return TriageReport(
        incident=Incident(
            id="incident-1",
            service="checkout",
            alerts=(Alert(service="checkout", fired_at=NOON, source_id="a"),),
        ),
        subject="checkout is failing",
        body="Two alerts in thirty minutes.",
    )


def test_an_in_memory_implementation_satisfies_the_port() -> None:
    notifier: Notifier = InMemoryNotifier()

    assert isinstance(notifier, Notifier)


def test_the_port_takes_one_report_at_a_time() -> None:
    notifier = InMemoryNotifier()

    notifier.deliver(_report())

    assert [delivered.incident_id for delivered in notifier.delivered] == ["incident-1"]


def test_a_delivery_failure_has_one_error_type_to_catch() -> None:
    """A caller handles it without importing anything channel-specific."""
    assert issubclass(NotifierError, Exception)
    assert NotifierError.__module__ == "alert_triage.ports.notifier"


def test_the_notifier_is_synchronous() -> None:
    """The port makes ordinary blocking calls; no caller needs an event loop."""
    assert not inspect.iscoroutinefunction(InMemoryNotifier.deliver)
    assert not inspect.iscoroutinefunction(Notifier.deliver)


def test_the_port_speaks_only_the_domain_s_vocabulary() -> None:
    """No channel type appears in the signature a caller programs against."""
    annotations = [
        parameter.annotation
        for parameter in inspect.signature(Notifier.deliver).parameters.values()
    ]

    assert all(
        annotation in {inspect.Parameter.empty, TriageReport}
        for annotation in annotations
    ), annotations


def test_delivering_answers_nothing_a_caller_would_have_to_inspect() -> None:
    """Success is returning; failure is raising. There is no third outcome."""
    signature = inspect.signature(Notifier.deliver)

    assert signature.return_annotation in {None, "None"}
