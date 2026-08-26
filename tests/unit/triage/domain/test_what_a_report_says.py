"""What an incident is worth saying, given what was learned about it.

Which report an incident earns is decided by whether findings exist, and the
wording of each is asserted here: the pass-through report explains its own
emptiness, and the investigated one leads with what was found.
"""

from datetime import UTC, datetime, timedelta

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
    return build_report(incident, None, examined=EVERY_SIGNAL)


EVERY_SIGNAL = tuple(Signal)


def _investigated(
    incident: Incident,
    findings: Findings,
    examined: tuple[Signal, ...] = EVERY_SIGNAL,
) -> TriageReport:
    """The report an incident gets when one did."""
    return build_report(incident, findings, examined=examined)


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


def test_an_investigation_that_found_nothing_names_every_signal_it_examined() -> None:
    """'Nothing notable' is only interpretable against the scope it covered."""
    body = _investigated(_incident(), Findings()).body.lower()

    for signal in EVERY_SIGNAL:
        assert signal.value in body


def test_a_report_claims_no_signal_that_was_not_examined() -> None:
    body = _investigated(
        _incident(), Findings(), examined=(Signal.LOGS, Signal.TRACE)
    ).body.lower()

    assert Signal.APM.value not in body
    assert Signal.INFRASTRUCTURE.value not in body


def test_the_account_of_what_was_examined_widens_with_the_crew() -> None:
    """A specialist joining the crew widens the wording rather than dating it."""
    incident = _incident()

    alone = _investigated(incident, Findings(), examined=(Signal.LOGS,)).body
    whole = _investigated(incident, Findings(), examined=EVERY_SIGNAL).body

    assert alone != whole
    assert Signal.INFRASTRUCTURE.value in whole.lower()
    assert Signal.INFRASTRUCTURE.value not in alone.lower()


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

    assert build_report(incident, None, examined=EVERY_SIGNAL) == _uninvestigated(
        incident
    )
    assert build_report(incident, Findings(), examined=EVERY_SIGNAL) == _investigated(
        incident, Findings()
    )


def test_no_findings_is_not_the_same_as_findings_that_are_empty() -> None:
    """One says nobody looked; the other says somebody looked and it was clean."""
    incident = _incident()

    assert (
        build_report(incident, None, examined=EVERY_SIGNAL).body
        != build_report(incident, Findings(), examined=EVERY_SIGNAL).body
    )


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


LOG_LINK = "https://app.datadoghq.com/logs?query=service%3Acheckout&event=AQAAA"


def _evidence_lines(body: str) -> list[str]:
    """The indented lines beneath a finding, which is where evidence renders."""
    return [line.strip() for line in body.splitlines() if line.startswith("    ")]


def test_evidence_carrying_an_address_renders_it_on_its_own_line() -> None:
    """A reader who wants to see the finding for themselves goes from here."""
    findings = Findings(
        findings=(
            _finding(examples=(_item(summary="container OOMKilled", url=LOG_LINK),)),
        )
    )

    lines = _evidence_lines(_investigated(_incident(), findings).body)

    assert lines == [f"{NOON.isoformat()} container OOMKilled", LOG_LINK]


def test_evidence_with_no_address_renders_exactly_as_it_did_before() -> None:
    """No address is a complete answer, and the report notes no absence."""
    findings = Findings(findings=(_finding(examples=(_item(summary="OOMKilled"),)),))

    lines = _evidence_lines(_investigated(_incident(), findings).body)

    assert lines == [f"{NOON.isoformat()} OOMKilled"]


def test_an_address_is_rendered_whole_beside_a_summary_that_was_shortened() -> None:
    """The failure this exists to fix: half a URL still reads as a link."""
    shortened = f"{'word ' * 60}…"
    findings = Findings(
        findings=(_finding(examples=(_item(summary=shortened, url=LOG_LINK),)),)
    )

    read, address = _evidence_lines(_investigated(_incident(), findings).body)

    assert address == LOG_LINK
    assert read.endswith("…")
    assert LOG_LINK not in read


def test_an_aggregates_address_stands_on_a_line_of_its_own_too() -> None:
    """An item with no instant is an aggregate, and is still somewhere to go."""
    aggregate = EvidenceItem(
        id="call-1",
        instant=None,
        summary="4200 errors in the window",
        payload={"count": 4200},
        url=LOG_LINK,
    )
    findings = Findings(findings=(_finding(examples=(aggregate,)),))

    lines = _evidence_lines(_investigated(_incident(), findings).body)

    assert lines == ["4200 errors in the window", LOG_LINK]
