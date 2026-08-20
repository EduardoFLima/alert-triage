from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.domain.alert import Alert
from alert_triage.domain.findings import Finding, Findings, LogRecord, Signal
from alert_triage.domain.incident import Incident
from alert_triage.domain.report import (
    NOT_INVESTIGATED,
    TriageReport,
    build_report,
)

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _uninvestigated(incident: Incident) -> TriageReport:
    """The report an incident gets when no investigation ever completed."""
    return build_report(incident, None)


def _investigated(incident: Incident, findings: Findings) -> TriageReport:
    """The report an incident gets when one did."""
    return build_report(incident, findings)


def _incident(incident_id: str = "incident-1", service: str = "checkout") -> Incident:
    return Incident(
        id=incident_id,
        service=service,
        alerts=(Alert(service=service, fired_at=NOON, source_id="a"),),
    )


def _report(
    subject: str = "checkout is failing", body: str = "Two alerts."
) -> TriageReport:
    return TriageReport(incident=_incident(), subject=subject, body=body)


def test_a_report_concerns_one_incident() -> None:
    incident = _incident()

    assert TriageReport(incident=incident, subject="s", body="b").incident == incident


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
    """Channel formatting lives in the adapter: a new channel changes nothing here."""
    carried = {field.name for field in fields(TriageReport)}
    derived = {name for name in dir(TriageReport) if not name.startswith("_")}

    assert carried == {"incident", "subject", "body"}
    assert derived == {"incident_id", "service"}


def test_a_report_is_a_value_and_cannot_be_edited_after_the_fact() -> None:
    report = _report()

    with pytest.raises(FrozenInstanceError):
        report.subject = "something else"  # type: ignore[misc]


def _fired(minutes: int, title: str, link: str) -> Alert:
    return Alert(
        service="checkout",
        fired_at=NOON + timedelta(minutes=minutes),
        source_id=f"alert-{minutes}",
        title=title,
        link=link,
    )


def _firing_incident(*alerts: Alert) -> Incident:
    return Incident(id="incident-1", service="checkout", alerts=alerts)


def test_a_pass_through_report_names_the_service_in_its_subject() -> None:
    report = _uninvestigated(_firing_incident(_fired(0, "Latency", "l/1")))

    assert "checkout" in report.subject


def test_a_pass_through_report_lists_every_alert_with_its_time_and_link() -> None:
    alerts = (
        _fired(0, "Latency above 2s", "https://platform/event/1"),
        _fired(5, "Error rate climbing", "https://platform/event/2"),
        _fired(20, "Checkout timing out", "https://platform/event/3"),
    )

    body = _uninvestigated(_firing_incident(*alerts)).body

    for alert in alerts:
        assert alert.title in body
        assert alert.link in body
        assert alert.fired_at.isoformat() in body


def test_a_pass_through_report_concerns_the_incident_it_was_built_from() -> None:
    incident = _firing_incident(_fired(0, "Latency", "l/1"))

    assert _uninvestigated(incident).incident == incident


def test_a_pass_through_report_says_investigation_could_not_complete() -> None:
    """The report of last resort: it explains its own emptiness, not poses as triage."""
    body = _uninvestigated(_firing_incident(_fired(0, "Latency", "l/1"))).body

    assert "could not complete" in body
    assert "attempted" in body


def test_an_alert_with_no_title_and_no_link_is_still_listed() -> None:
    """Both are optional on an ``Alert``; a source that supplies neither is fine."""
    alert = Alert(service="checkout", fired_at=NOON, source_id="bare")

    body = _uninvestigated(_firing_incident(alert)).body

    assert alert.fired_at.isoformat() in body
    assert "no title" in body
    assert "no link" in body


def test_the_subject_survives_a_service_tag_that_spans_two_lines() -> None:
    """A subject is one line whatever the platform tagged the alerts with."""
    incident = Incident(
        id="incident-1",
        service="check\nout",
        alerts=(Alert(service="check\nout", fired_at=NOON, source_id="a"),),
    )

    assert "\n" not in _uninvestigated(incident).subject


def _record(offset: timedelta = timedelta(), message: str = "OOMKilled") -> LogRecord:
    return LogRecord(
        timestamp=NOON + offset, level="ERROR", message=message, service="checkout"
    )


def _finding(
    observation: str = "OOMKilled recurs every 40s",
    occurrences: int = 47,
    examples: tuple[LogRecord, ...] = (),
) -> Finding:
    return Finding(
        signal=Signal.LOGS,
        observation=observation,
        occurrences=occurrences,
        examples=examples or (_record(),),
    )


def test_an_investigated_report_names_the_service_in_its_subject() -> None:
    report = _investigated(_incident(), Findings(findings=(_finding(),)))

    assert "checkout" in report.subject


def test_an_investigated_report_states_what_was_found() -> None:
    findings = Findings(findings=(_finding(observation="OOMKilled recurs every 40s"),))

    body = _investigated(_incident(), findings).body

    assert "OOMKilled recurs every 40s" in body


def test_an_investigated_report_carries_the_evidence_behind_each_finding() -> None:
    findings = Findings(
        findings=(_finding(examples=(_record(message="container OOMKilled"),)),)
    )

    body = _investigated(_incident(), findings).body

    assert "container OOMKilled" in body
    assert NOON.isoformat() in body


def test_an_investigated_report_says_how_often_the_pattern_occurred() -> None:
    """The count is what survives when only a handful of records travel with it."""
    findings = Findings(findings=(_finding(occurrences=47),))

    assert "47" in _investigated(_incident(), findings).body


def test_an_investigated_report_still_lists_the_alerts() -> None:
    incident = Incident(
        id="incident-1",
        service="checkout",
        alerts=(
            Alert(service="checkout", fired_at=NOON, source_id="a", link="http://a"),
        ),
    )

    body = _investigated(incident, Findings(findings=(_finding(),))).body

    assert "http://a" in body


def test_an_investigation_that_found_nothing_notable_says_so() -> None:
    """Not an empty section: 'we looked and it is clean' is the news."""
    body = _investigated(_incident(), Findings()).body

    assert "nothing notable" in body.lower()
    assert NOT_INVESTIGATED not in body


def test_an_investigated_report_offers_no_conclusion() -> None:
    findings = Findings(findings=(_finding(),))

    body = _investigated(_incident(), findings).body.lower()

    assert "root cause" not in body
    assert "confidence" not in body
    assert "hypothesis" not in body


def test_an_investigated_report_concerns_the_incident_it_was_built_from() -> None:
    incident = _incident()

    report = _investigated(incident, Findings(findings=(_finding(),)))

    assert report.incident == incident


def test_the_report_for_an_incident_is_chosen_by_whether_there_are_findings() -> None:
    """Why an investigation failed is the run's business; a report only knows if."""
    incident = _incident()

    assert build_report(incident, None) == _uninvestigated(incident)
    assert build_report(incident, Findings()) == _investigated(incident, Findings())


def test_no_findings_is_not_the_same_as_findings_that_are_empty() -> None:
    """One says nobody looked; the other says somebody looked and it was clean."""
    incident = _incident()

    assert build_report(incident, None).body != build_report(incident, Findings()).body
