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
    assert _report().incident_id == "incident-1"


def test_a_report_carries_the_service_the_incident_is_about() -> None:
    assert _report().service == "checkout"


def test_a_subject_spanning_two_lines_is_refused() -> None:
    with pytest.raises(ValueError, match="single line"):
        _report(subject="checkout is failing\nand has been for an hour")


def test_a_report_needs_a_subject_to_announce_it() -> None:
    with pytest.raises(ValueError, match="subject"):
        _report(subject="   ")


def test_the_body_is_carried_verbatim_however_a_channel_would_have_to_escape_it() -> (
    None
):
    body = 'Latency > 2s & rising: {"p99": 4.1}\n<not markup>'

    assert _report(body=body).body == body


def test_a_report_renders_itself_for_no_channel() -> None:
    carried = {field.name for field in fields(TriageReport)}
    exposed = {name for name in dir(TriageReport) if not name.startswith("_")}

    assert carried == {"incident_id", "service", "subject", "body"}
    assert exposed == set(), "a report is four values and no way of presenting them"


def test_a_report_is_a_value_and_cannot_be_edited_after_the_fact() -> None:
    report = _report()

    with pytest.raises(FrozenInstanceError):
        report.subject = "something else"  # type: ignore[misc]
