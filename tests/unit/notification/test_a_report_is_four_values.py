"""What a report is, before any channel has looked at it.

A subject every channel can carry as one line, a body carried verbatim, and the
incident named rather than held. Nothing here knows how a report is built or
what it will be rendered into.
"""

from dataclasses import FrozenInstanceError, fields

import pytest

from alert_triage.notification.contract import TriageReport


def _report(
    subject: str = "checkout is failing", body: str = "Two alerts."
) -> TriageReport:
    return TriageReport(
        incident_id="incident-1",
        service="checkout",
        subject=subject,
        body=body,
    )


def test_a_report_carries_the_identifier_of_the_incident_it_concerns() -> None:
    """Two reports about different incidents are told apart without the alerts."""
    assert _report().incident_id == "incident-1"


def test_a_report_carries_the_service_the_incident_is_about() -> None:
    assert _report().service == "checkout"


def test_a_subject_spanning_two_lines_is_refused() -> None:
    """A subject is one line: an email header cannot carry a second one."""
    with pytest.raises(ValueError, match="single line"):
        _report(subject="checkout is failing\nand has been for an hour")


def test_a_report_needs_a_subject_to_announce_it() -> None:
    with pytest.raises(ValueError, match="subject"):
        _report(subject="   ")


def test_the_body_is_carried_verbatim_however_a_channel_would_have_to_escape_it() -> (
    None
):
    """The body is plain text; escaping it is the channel's problem, not this."""
    body = 'Latency > 2s & rising: {"p99": 4.1}\n<not markup>'

    assert _report(body=body).body == body


def test_a_report_renders_itself_for_no_channel() -> None:
    """Channel formatting lives in the adapter: a new channel changes nothing here.

    Four values and no method: delivery needs an identifier and a service, not
    the aggregate behind them, and the day a ``render`` or ``as_email`` lands
    here is the day a channel's work started leaking into the contract. This is
    what fails on that day.
    """
    carried = {field.name for field in fields(TriageReport)}
    exposed = {name for name in dir(TriageReport) if not name.startswith("_")}

    assert carried == {"incident_id", "service", "subject", "body"}
    assert exposed == set(), "a report is four values and no way of presenting them"


def test_a_report_is_a_value_and_cannot_be_edited_after_the_fact() -> None:
    report = _report()

    with pytest.raises(FrozenInstanceError):
        report.subject = "something else"  # type: ignore[misc]
