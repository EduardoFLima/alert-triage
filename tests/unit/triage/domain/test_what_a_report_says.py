"""What an incident is worth saying, given what was learned about it.

Which report an incident earns is decided by whether an investigation completed,
and that decision is asserted here. What the investigation had to say for itself
is not: it arrives already worded, and what an account shows is established
beside the renderer that builds one.

What is left here is what only triage knows — the subject that marks the sender,
the alerts that fired, and the report of last resort for an incident nothing
managed to look at.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from alert_triage.configuration.settings import ScopedService
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
from alert_triage.triage.domain.report import (
    CRITICAL_MARKER,
    NOT_INVESTIGATED,
    build_report,
)

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
UNDESCRIBED = ScopedService(name="checkout")


EVERY_SIGNAL = tuple(Signal)


def _uninvestigated(incident: Incident) -> TriageReport:
    """The report an incident gets when no investigation ever completed."""
    return build_report(incident, None, UNDESCRIBED)


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
    """A diagnosis whose account is composed the way a real one is.

    Worded through the real renderer rather than hand-written, so these
    assertions are about what a report carries rather than about the fixture
    that fed it.
    """
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
    """The report an incident gets when one did."""
    return build_report(incident, diagnosis or _diagnosis(), UNDESCRIBED)


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


def test_a_report_announces_the_incident_in_the_investigations_words() -> None:
    report = _investigated(_incident())

    assert report.subject.endswith("checkout is out of memory")
    assert report.subject.startswith("[alert-triage]")


def test_an_investigated_report_carries_the_account_it_was_given() -> None:
    report = _investigated(
        _incident(), _diagnosis(narrative="The pods keep dying under load.")
    )

    assert "The pods keep dying under load." in report.body


def test_an_investigated_report_states_the_confidence_it_was_given() -> None:
    """Stated by the renderer, so it reaches a reader whatever the writer wrote."""
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
    """Why an investigation failed is the run's business; a report only knows if."""
    incident = _incident()

    assert build_report(incident, None, UNDESCRIBED) == _uninvestigated(incident)
    assert build_report(incident, _diagnosis(), UNDESCRIBED) == _investigated(incident)


def test_no_investigation_is_not_the_same_as_one_that_found_nothing() -> None:
    """One says nobody looked; the other says somebody looked and it was clean."""
    incident = _incident()
    clean = _diagnosis(
        findings=Findings(consulted=EVERY_SIGNAL),
        narrative="The logs, apm, trace and infrastructure were examined.",
        hypothesis=None,
        confidence=None,
    )

    assert (
        build_report(incident, None, UNDESCRIBED).body
        != build_report(incident, clean, UNDESCRIBED).body
    )


def test_the_last_resort_report_carries_no_hypothesis_and_no_confidence() -> None:
    """Nothing produced one, and a report must never invent what it was not given."""
    body = _uninvestigated(_incident()).body.lower()

    assert NOT_INVESTIGATED in _uninvestigated(_incident()).body
    assert "hypothesis" not in body
    assert "confidence" not in body


def test_the_report_does_not_pretend_to_conclude_on_a_failed_investigation() -> None:
    incident = _incident()

    assert _uninvestigated(incident).body != _investigated(incident).body
    assert NOT_INVESTIGATED not in _investigated(incident).body


def test_triage_does_not_read_the_investigations_vocabulary_to_build_a_body() -> None:
    """The account arrives written; a finding's shape is no longer triage's business."""
    import alert_triage.triage.domain.report as report_module

    source = Path(report_module.__file__).read_text()

    assert "EvidenceItem" not in source
    assert "Finding" not in source
    assert "Signal" not in source


def test_a_report_about_a_critical_service_says_so_in_its_subject() -> None:
    """A reader scanning subjects can tell which one to open first."""
    incident = _incident()
    critical = ScopedService(name="checkout", critical=True)

    investigated = build_report(incident, _diagnosis(), critical)
    passed_through = build_report(incident, None, critical)

    assert CRITICAL_MARKER in investigated.subject
    assert CRITICAL_MARKER in passed_through.subject


def test_an_ordinary_services_subject_is_what_it_has_always_been() -> None:
    """The marking means something by its absence as well as its presence."""
    incident = _incident()
    ordinary = ScopedService(name="checkout")

    assert (
        build_report(incident, _diagnosis(), ordinary).subject
        == _investigated(incident).subject
    )
    assert (
        build_report(incident, None, ordinary).subject
        == _uninvestigated(incident).subject
    )


def test_criticality_marks_the_subject_and_nothing_beneath_it() -> None:
    """It announces the report; it is not something an investigation found."""
    incident = _incident()
    critical = ScopedService(name="checkout", critical=True)

    assert (
        build_report(incident, _diagnosis(), critical).body
        == _investigated(incident).body
    )
    assert build_report(incident, None, critical).body == _uninvestigated(incident).body
