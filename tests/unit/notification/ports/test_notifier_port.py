import inspect

from alert_triage.notification.contract import TriageReport
from alert_triage.notification.ports.notifier import Notifier, NotifierError


class InMemoryNotifier:
    """What a test double for the port looks like: reports, no destination."""

    def deliver(self, report: TriageReport) -> None:
        """Accept the report, as a destination that is always reachable would."""


def test_a_delivery_failure_has_one_error_type_to_catch() -> None:
    """A caller handles it without importing anything channel-specific."""
    assert issubclass(NotifierError, Exception)
    assert NotifierError.__module__ == "alert_triage.notification.ports.notifier"


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

    assert annotations == [inspect.Parameter.empty, TriageReport]


def test_delivering_answers_nothing_a_caller_would_have_to_inspect() -> None:
    """Success is returning; failure is raising. There is no third outcome."""
    signature = inspect.signature(Notifier.deliver)

    assert signature.return_annotation in {None, "None"}
