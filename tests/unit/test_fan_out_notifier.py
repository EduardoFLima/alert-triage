import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from alert_triage.adapters.fan_out import FanOutNotifier
from alert_triage.domain.report import TriageReport
from alert_triage.ports.notifier import Notifier, NotifierError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


@dataclass
class RecordingChannel:
    """A channel that remembers every attempt, and fails when told to."""

    name: str = "channel"
    failure: Exception | None = None
    attempts: list[TriageReport] = field(default_factory=list)

    def deliver(self, report: TriageReport) -> None:
        """Record the attempt, then fail if this channel was told to."""
        self.attempts.append(report)
        if self.failure is not None:
            raise self.failure


def _failing(name: str, reason: str) -> RecordingChannel:
    return RecordingChannel(name=name, failure=NotifierError(reason))


def _report() -> TriageReport:
    return TriageReport(
        incident_id="incident-1",
        service="checkout",
        subject="checkout is failing",
        body="Two alerts in thirty minutes.",
    )


def test_the_fan_out_is_itself_a_notifier() -> None:
    """A caller injects one notifier and never learns how many sit behind it."""
    notifier: Notifier = FanOutNotifier([RecordingChannel()])

    assert isinstance(notifier, Notifier)


def test_the_report_reaches_every_configured_channel_exactly_once() -> None:
    channels = [RecordingChannel(name="email"), RecordingChannel(name="teams")]

    FanOutNotifier(channels).deliver(_report())

    assert [len(channel.attempts) for channel in channels] == [1, 1]


def test_a_channel_failing_does_not_stop_a_later_one_from_being_attempted() -> None:
    failing = _failing("email", "relay is down")
    working = RecordingChannel(name="teams")

    FanOutNotifier([failing, working]).deliver(_report())

    assert len(working.attempts) == 1


def test_every_channel_is_attempted_even_when_one_of_them_fails() -> None:
    channels = [
        RecordingChannel(name="first"),
        _failing("second", "refused"),
        RecordingChannel(name="third"),
    ]

    FanOutNotifier(channels).deliver(_report())

    assert [len(channel.attempts) for channel in channels] == [1, 1, 1]


def test_delivery_succeeds_when_at_least_one_channel_accepted_the_report() -> None:
    """The team has been told, which is what the ledger's next question turns on."""
    FanOutNotifier([_failing("email", "relay is down"), RecordingChannel()]).deliver(
        _report()
    )


def test_a_partial_failure_is_surfaced_rather_than_discarded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        FanOutNotifier(
            [_failing("email", "relay is down"), RecordingChannel()]
        ).deliver(_report())

    assert "relay is down" in caplog.text
    assert "incident-1" in caplog.text


def test_delivery_fails_when_every_channel_failed() -> None:
    channels = [_failing("email", "relay is down"), _failing("teams", "flow rejected")]

    with pytest.raises(NotifierError):
        FanOutNotifier(channels).deliver(_report())


def test_the_failure_accounts_for_every_channel_not_only_the_last() -> None:
    """An operator debugging "no reports arrive" needs both reasons at once."""
    channels = [_failing("email", "relay is down"), _failing("teams", "flow rejected")]

    with pytest.raises(NotifierError) as raised:
        FanOutNotifier(channels).deliver(_report())

    assert "relay is down" in str(raised.value)
    assert "flow rejected" in str(raised.value)


def test_a_total_failure_names_the_incident_that_reached_nobody() -> None:
    with pytest.raises(NotifierError, match="incident-1"):
        FanOutNotifier([_failing("email", "down")]).deliver(_report())


def test_a_failing_channel_is_not_retried_in_place() -> None:
    """Retry is the next run's job: the ledger is the durable retry mechanism."""
    failing = _failing("email", "relay is down")

    with pytest.raises(NotifierError):
        FanOutNotifier([failing]).deliver(_report())

    assert len(failing.attempts) == 1


def test_a_channel_failing_in_a_way_the_port_did_not_promise_is_still_survived() -> (
    None
):
    """A channel that raises anything at all must not take the others down with it."""
    reckless = RecordingChannel(name="reckless", failure=RuntimeError("boom"))
    working = RecordingChannel(name="teams")

    FanOutNotifier([reckless, working]).deliver(_report())

    assert len(working.attempts) == 1


def test_a_fan_out_over_no_channel_at_all_is_refused_when_it_is_built() -> None:
    """A notifier that can tell nobody anything is a mistake, found at startup."""
    with pytest.raises(ValueError, match="at least one"):
        FanOutNotifier([])
