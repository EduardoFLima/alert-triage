from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.investigation.contract import EvidenceItem, Finding, Findings, Signal
from alert_triage.notification.contract import TriageReport
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.incident import Incident
from alert_triage.triage.domain.report import (
    EVIDENCE_INCOMPLETE,
    NOT_INVESTIGATED,
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
    incident = _incident()
    return TriageReport(
        incident_id=incident.id,
        service=incident.service,
        subject=subject,
        body=body,
    )


def test_a_report_names_the_incident_it_concerns_without_carrying_it() -> None:
    """Delivery needs an identifier and a service, not the aggregate behind them."""
    report = TriageReport(
        incident_id="incident-1", service="checkout", subject="s", body="b"
    )

    assert (report.incident_id, report.service) == ("incident-1", "checkout")
    assert {field.name for field in fields(TriageReport)} == {
        "incident_id",
        "service",
        "subject",
        "body",
    }


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
    exposed = {name for name in dir(TriageReport) if not name.startswith("_")}

    assert carried == {"incident_id", "service", "subject", "body"}
    assert exposed == set(), "a report is four values and no way of presenting them"


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


def test_a_pass_through_report_names_the_incident_it_was_built_from() -> None:
    incident = _firing_incident(_fired(0, "Latency", "l/1"))

    report = _uninvestigated(incident)

    assert (report.incident_id, report.service) == (incident.id, incident.service)


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


def _item(offset: timedelta = timedelta(), summary: str = "OOMKilled") -> EvidenceItem:
    return EvidenceItem(
        id="call-1/item-1",
        instant=NOON + offset,
        summary=summary,
        payload={"message": summary},
    )


def _finding(
    observation: str = "OOMKilled recurs every 40s",
    occurrences: int = 47,
    examples: tuple[EvidenceItem, ...] = (),
) -> Finding:
    return Finding(
        signal=Signal.LOGS,
        observation=observation,
        occurrences=occurrences,
        examples=examples or (_item(),),
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
        findings=(_finding(examples=(_item(summary="container OOMKilled"),)),)
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


def test_an_investigated_report_names_the_incident_it_was_built_from() -> None:
    incident = _incident()

    report = _investigated(incident, Findings(findings=(_finding(),)))

    assert (report.incident_id, report.service) == (incident.id, incident.service)


def test_the_report_for_an_incident_is_chosen_by_whether_there_are_findings() -> None:
    """Why an investigation failed is the run's business; a report only knows if."""
    incident = _incident()

    assert build_report(incident, None) == _uninvestigated(incident)
    assert build_report(incident, Findings()) == _investigated(incident, Findings())


def test_no_findings_is_not_the_same_as_findings_that_are_empty() -> None:
    """One says nobody looked; the other says somebody looked and it was clean."""
    incident = _incident()

    assert build_report(incident, None).body != build_report(incident, Findings()).body


def test_an_investigated_report_reads_an_aggregate_with_no_instant() -> None:
    """A flame graph concerns a window, not a moment; it is still evidence."""
    aggregate = EvidenceItem(
        id="call-2",
        instant=None,
        summary="one handler holds 84% of the time",
        payload={},
    )

    body = _investigated(
        _incident(), Findings(findings=(_finding(examples=(aggregate,)),))
    ).body

    assert "one handler holds 84% of the time" in body


def test_a_report_whose_investigation_could_not_see_everything_says_so() -> None:
    findings = Findings(
        findings=(_finding(observation="OOMKilled recurs every 40s"),),
        retrieval_failures=("the log aggregation was refused",),
    )

    body = _investigated(_incident(), findings).body

    assert EVIDENCE_INCOMPLETE in body
    assert "OOMKilled recurs every 40s" in body


def test_an_incomplete_investigation_that_found_nothing_still_says_so() -> None:
    """The dangerous report: nothing found, and part of the looking never happened."""
    findings = Findings(retrieval_failures=("the log search was refused",))

    body = _investigated(_incident(), findings).body

    assert EVIDENCE_INCOMPLETE in body


def test_a_complete_investigation_carries_no_incompleteness_note() -> None:
    notable = Findings(findings=(_finding(),))
    quiet = Findings()

    assert EVIDENCE_INCOMPLETE not in _investigated(_incident(), notable).body
    assert EVIDENCE_INCOMPLETE not in _investigated(_incident(), quiet).body


def test_incomplete_evidence_is_not_the_report_for_a_failed_investigation() -> None:
    """One says part of the looking failed; the other says all of it did."""
    incomplete = _investigated(
        _incident(), Findings(retrieval_failures=("the log search was refused",))
    ).body
    uninvestigated = _uninvestigated(_incident()).body

    assert NOT_INVESTIGATED not in incomplete
    assert EVIDENCE_INCOMPLETE not in uninvestigated
    assert NOT_INVESTIGATED in uninvestigated
