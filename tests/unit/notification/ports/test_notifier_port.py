import inspect

from alert_triage.notification.contract import TriageReport
from alert_triage.notification.ports.notifier import Notifier, NotifierError


class InMemoryNotifier:
    def deliver(self, report: TriageReport) -> None:
        pass


def test_a_delivery_failure_has_one_error_type_to_catch() -> None:
    assert issubclass(NotifierError, Exception)
    assert NotifierError.__module__ == "alert_triage.notification.ports.notifier"


def test_the_notifier_is_synchronous() -> None:
    assert not inspect.iscoroutinefunction(InMemoryNotifier.deliver)
    assert not inspect.iscoroutinefunction(Notifier.deliver)


def test_the_port_speaks_only_the_domain_s_vocabulary() -> None:
    annotations = [
        parameter.annotation
        for parameter in inspect.signature(Notifier.deliver).parameters.values()
    ]

    assert annotations == [inspect.Parameter.empty, TriageReport]


def test_delivering_answers_nothing_a_caller_would_have_to_inspect() -> None:
    signature = inspect.signature(Notifier.deliver)

    assert signature.return_annotation in {None, "None"}
