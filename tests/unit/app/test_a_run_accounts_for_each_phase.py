"""A run, read back off the log by someone who was not watching it happen.

The phases are what a reader navigates by: an incident opens one, the
investigation of it is another, and what was delivered about it closes it. Each
announces itself, and each says what it concerns — a block that could belong to
any of three services is a block a reader has to correlate by hand.

What went wrong is read the same way, at the weight its consequence deserves: a
failure that ends the run is boxed like the phase it ended, and a failure
contained to one group is captioned under the phase it happened in.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.app.pipeline import run
from alert_triage.configuration.settings import (
    CircuitBreakers,
    Grouping,
    Ingestion,
    Investigation,
    Ledger,
    ReNotify,
    Scope,
    ScopedService,
)
from alert_triage.investigation.contract import (
    Confidence,
    Diagnosis,
    Findings,
    InvestigationTarget,
)
from alert_triage.investigation.ports.investigator import InvestigatorError
from alert_triage.notification.contract import TriageReport
from alert_triage.notification.ports.notifier import NotifierError
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.incident import Incident
from alert_triage.triage.ports.alert_source import AlertSourceError
from alert_triage.triage.ports.ledger import TriageLedgerError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
HEADLINE = "checkout is out of memory"


@dataclass(frozen=True)
class _Config:
    scope: Scope = field(default_factory=lambda: Scope(owner="sre"))
    grouping: Grouping = field(default_factory=Grouping)
    ingestion: Ingestion = field(default_factory=Ingestion)
    re_notify: ReNotify = field(default_factory=ReNotify)
    ledger: Ledger = field(default_factory=Ledger)
    circuit_breakers: CircuitBreakers = field(default_factory=CircuitBreakers)
    investigation: Investigation = field(default_factory=Investigation)


class _Source:
    def __init__(self, alerts: Sequence[Alert], failure: str | None = None) -> None:
        self._alerts = alerts
        self._failure = failure

    def fetch_since(self, since: datetime) -> Sequence[Alert]:
        if self._failure is not None:
            raise AlertSourceError(self._failure)
        return self._alerts


class _Ledger:
    def __init__(
        self, on_record: Sequence[Incident] = (), failure: str | None = None
    ) -> None:
        self._on_record = on_record
        self._failure = failure

    def open_incidents(self, service: str, now: datetime) -> Sequence[Incident]:
        if self._failure is not None:
            raise TriageLedgerError(self._failure)
        return [one for one in self._on_record if one.service == service]

    def record(self, incident: Incident, now: datetime) -> None:
        return None


class _Notifier:
    def __init__(self, failure: str | None = None) -> None:
        self._failure = failure

    def deliver(self, report: TriageReport) -> None:
        if self._failure is not None:
            raise NotifierError(self._failure)


class _Investigator:
    def __init__(self, failure: str | None = None) -> None:
        self._failure = failure

    def investigate(self, target: InvestigationTarget) -> Diagnosis:
        if self._failure is not None:
            raise InvestigatorError(self._failure)
        return Diagnosis(
            headline=HEADLINE,
            account="The pods are being killed.",
            hypothesis="a memory leak",
            confidence=Confidence.HIGH,
            findings=Findings(),
        )


def _alert(source_id: str, offset: timedelta = timedelta()) -> Alert:
    return Alert(
        service="checkout",
        fired_at=NOON + offset,
        source_id=source_id,
        title=f"checkout alert {source_id}",
        link=f"https://platform/event/{source_id}",
    )


def _report(
    incident: Incident, diagnosis: Diagnosis | None, service: ScopedService
) -> TriageReport:
    return TriageReport(
        service=incident.service,
        subject=diagnosis.headline if diagnosis else "nothing was found",
        body="what happened",
        incident_id=incident.id,
    )


def _ran(
    caplog: pytest.LogCaptureFixture,
    *,
    on_record: Sequence[Incident] = (),
    source: _Source | None = None,
    ledger: _Ledger | None = None,
    notifier: _Notifier | None = None,
    investigator: _Investigator | None = None,
    config: _Config | None = None,
) -> str:
    with caplog.at_level(logging.INFO):
        run(
            source=source or _Source([_alert("a"), _alert("b", timedelta(minutes=3))]),
            ledger=ledger or _Ledger(on_record),
            notifier=notifier or _Notifier(),
            investigator=investigator or _Investigator(),
            build_report=_report,
            config=config or _Config(),
            now=NOON + timedelta(minutes=10),
            new_id=lambda: "incident-1",
        )
    return " ".join(caplog.text.split())


def test_each_phase_of_a_run_announces_itself(
    caplog: pytest.LogCaptureFixture,
) -> None:
    written = _ran(caplog)

    assert "INCIDENT · checkout" in written
    assert "INVESTIGATING · checkout" in written
    assert "REPORTING · checkout" in written


def test_an_incident_block_says_what_it_is_about(
    caplog: pytest.LogCaptureFixture,
) -> None:
    written = _ran(caplog)

    assert "alerts 2" in written


def test_what_a_run_grouped_is_written_down_before_any_of_it_is_handled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    written = _ran(caplog)

    assert "fetched 2" in written
    assert "incidents 1" in written


def test_what_was_delivered_is_written_down_in_the_words_a_team_receives(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The headline is the report; a reader should not have to open their email."""
    written = _ran(caplog)

    assert HEADLINE in written
    assert "incident-1" in written


def test_a_report_nobody_is_owed_says_why_rather_than_going_quiet(
    caplog: pytest.LogCaptureFixture,
) -> None:
    on_record = Incident(
        id="incident-0",
        service="checkout",
        alerts=(_alert("a"),),
        last_reported_at=NOON,
    )

    written = _ran(caplog, on_record=(on_record,))

    assert "REPORTING · checkout" in written
    assert "cooldown" in written


def test_a_failure_that_ends_the_run_is_boxed_like_the_phase_it_ended(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Nothing follows it, so nothing else will tell a reader why the log stops."""
    written = _ran(caplog, source=_Source([], "the platform refused the search"))

    assert "│ FETCH FAILED" in written
    assert "the platform refused the search" in written


def test_a_failure_contained_to_one_group_is_captioned_under_its_phase(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The groups after it still get their reports, so it is not the run ending."""
    written = _ran(caplog, ledger=_Ledger(failure="the ledger is unreadable"))

    assert "╭" not in written.split("INCIDENT · checkout")[-1].split("──")[0]
    assert "── the ledger could not be read" in written
    assert "the ledger is unreadable" in written


def test_an_investigation_that_failed_says_so_where_it_was_running(
    caplog: pytest.LogCaptureFixture,
) -> None:
    written = _ran(caplog, investigator=_Investigator("the manager errored"))

    assert "── the investigation failed" in written
    assert "the manager errored" in written


def test_a_report_no_channel_took_says_so_where_it_was_delivered(
    caplog: pytest.LogCaptureFixture,
) -> None:
    written = _ran(caplog, notifier=_Notifier("no channel accepted it"))

    assert "── the report was not delivered" in written
    assert "no channel accepted it" in written


def test_an_incident_left_alone_says_the_acceptable_latency_is_why(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A reader must tell an incident nobody looked at from one nobody saw."""
    quiet = [
        replace(_alert("a"), observed_latency_ms=100),
        replace(_alert("b", timedelta(minutes=3)), observed_latency_ms=180),
    ]
    watching = _Config(
        scope=Scope(
            owner="sre",
            services=(ScopedService(name="checkout", acceptable_latency_ms=250),),
        )
    )

    written = _ran(caplog, source=_Source(quiet), config=watching)

    assert "REPORTING · checkout" in written
    assert "acceptable latency" in written
    assert "250" in written
    assert "incident-1" in written
