from datetime import UTC, datetime, timedelta
from pathlib import Path

from alert_triage.investigation.contract import (
    Confidence,
    Diagnosis,
    EvidenceItem,
    Finding,
    Findings,
    Signal,
)
from alert_triage.investigation.domain.account import compose
from alert_triage.notification.contract import TriageReport
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.incident import Incident
from alert_triage.triage.domain.report import NOT_INVESTIGATED, build_report

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

PROD = "prod"


EVERY_SIGNAL = tuple(Signal)


def _uninvestigated(incident: Incident) -> TriageReport:
    return build_report(incident, None, PROD)


def _finding(observation: str = "OOMKilled recurs every 40s") -> Finding:
    return Finding(
        signal=Signal.LOGS,
        observation=observation,
        occurrences=47,
        examples=(
            EvidenceItem(
                id="call-1/item-1",
                instant=NOON,
                summary="container OOMKilled",
                payload={},
            ),
        ),
    )


def _diagnosis(
    findings: Findings | None = None,
    headline: str = "checkout is out of memory",
    narrative: str = "The pods keep dying under load.",
    hypothesis: str | None = "the container memory limit is too low",
    confidence: Confidence | None = Confidence.HIGH,
) -> Diagnosis:
    found = (
        findings
        if findings is not None
        else Findings(findings=(_finding(),), consulted=EVERY_SIGNAL)
    )
    return Diagnosis(
        headline=headline,
        account=compose(narrative, found, confidence),
        hypothesis=hypothesis,
        confidence=confidence,
        findings=found,
    )


def _investigated(
    incident: Incident, diagnosis: Diagnosis | None = None
) -> TriageReport:
    return build_report(incident, diagnosis or _diagnosis(), PROD)


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
    body = _uninvestigated(_firing_incident(_fired(0, "Latency", "l/1"))).body

    assert "could not complete" in body
    assert "attempted" in body


def test_an_alert_with_no_title_and_no_link_is_still_listed() -> None:
    alert = Alert(service="checkout", fired_at=NOON, source_id="bare")

    body = _uninvestigated(_firing_incident(alert)).body

    assert alert.fired_at.isoformat() in body
    assert "no title" in body
    assert "no link" in body


def test_the_subject_survives_a_service_tag_that_spans_two_lines() -> None:
    incident = Incident(
        id="incident-1",
        service="check\nout",
        alerts=(Alert(service="check\nout", fired_at=NOON, source_id="a"),),
    )

    assert "\n" not in _uninvestigated(incident).subject


def _item(
    offset: timedelta = timedelta(),
    summary: str = "OOMKilled",
    url: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        id="call-1/item-1",
        instant=NOON + offset,
        summary=summary,
        payload={"message": summary},
        url=url,
    )


def test_an_investigated_report_carries_the_account_it_was_given() -> None:
    report = _investigated(
        _incident(), _diagnosis(narrative="The pods keep dying under load.")
    )

    assert "The pods keep dying under load." in report.body


def test_an_investigated_report_states_the_confidence_it_was_given() -> None:
    report = _investigated(_incident(), _diagnosis(confidence=Confidence.LOW))

    assert Confidence.LOW.value in report.body
    assert Confidence.HIGH.value not in report.body


def test_the_conclusion_does_not_displace_what_it_was_drawn_from() -> None:
    report = _investigated(_incident(), _diagnosis())

    assert "OOMKilled recurs every 40s" in report.body
    assert "container OOMKilled" in report.body


def test_an_investigated_report_still_lists_the_alerts() -> None:
    incident = Incident(
        id="incident-1",
        service="checkout",
        alerts=(
            Alert(service="checkout", fired_at=NOON, source_id="a", link="http://a"),
        ),
    )

    assert "http://a" in _investigated(incident).body


def test_an_investigated_report_names_the_incident_it_was_built_from() -> None:
    incident = _incident()

    report = _investigated(incident)

    assert (report.incident_id, report.service) == (incident.id, incident.service)


def test_the_report_for_an_incident_is_chosen_by_whether_one_completed() -> None:
    incident = _incident()

    assert build_report(incident, None, PROD) == _uninvestigated(incident)
    assert build_report(incident, _diagnosis(), PROD) == _investigated(incident)


def test_no_investigation_is_not_the_same_as_one_that_found_nothing() -> None:
    incident = _incident()
    clean = _diagnosis(
        findings=Findings(consulted=EVERY_SIGNAL),
        narrative="The logs, apm, trace and infrastructure were examined.",
        hypothesis=None,
        confidence=None,
    )

    assert (
        build_report(incident, None, PROD).body
        != build_report(incident, clean, PROD).body
    )


def test_the_last_resort_report_carries_no_hypothesis_and_no_confidence() -> None:
    body = _uninvestigated(_incident()).body.lower()

    assert NOT_INVESTIGATED in _uninvestigated(_incident()).body
    assert "hypothesis" not in body
    assert "confidence" not in body


def test_the_report_does_not_pretend_to_conclude_on_a_failed_investigation() -> None:
    incident = _incident()

    assert _uninvestigated(incident).body != _investigated(incident).body
    assert NOT_INVESTIGATED not in _investigated(incident).body


def test_triage_does_not_read_the_investigations_vocabulary_to_build_a_body() -> None:
    import alert_triage.triage.domain.report as report_module

    source = Path(report_module.__file__).read_text()

    assert "EvidenceItem" not in source
    assert "Finding" not in source
    assert "Signal" not in source


def test_a_pass_through_report_names_the_environment_after_its_prefix() -> None:
    report = _uninvestigated(_incident())

    assert report.subject.startswith("[alert-triage] [prod] checkout")


def test_an_investigated_report_names_the_environment_after_its_prefix() -> None:
    report = _investigated(_incident())

    assert report.subject == "[alert-triage] [prod] checkout is out of memory"


def test_a_pass_through_reports_first_sentence_names_the_environment() -> None:
    first_sentence = _uninvestigated(_incident()).body.splitlines()[0]

    assert "service checkout in prod" in first_sentence


def test_an_investigated_reports_first_sentence_names_the_environment() -> None:
    first_sentence = _investigated(_incident()).body.splitlines()[0]

    assert "service checkout in prod" in first_sentence


def test_two_deployments_reports_on_one_service_differ_by_subject_alone() -> None:
    incident = _incident()

    assert (
        build_report(incident, None, "prod").subject
        != build_report(incident, None, "staging").subject
    )
