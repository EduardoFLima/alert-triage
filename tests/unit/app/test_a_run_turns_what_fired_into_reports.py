"""One run, from the alerts it fetched to the incidents it recorded.

The happy path and the arithmetic around it: which window is asked for,
which instant reaches the records, and what a second run over the same
inputs decides.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.app.pipeline import RunOutcome, run
from alert_triage.configuration.port import Config
from alert_triage.configuration.settings import (
    CircuitBreakers,
    Grouping,
    Ingestion,
    Investigation,
    Ledger,
    ReNotify,
    Scope,
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
from alert_triage.triage.domain.report import NOT_INVESTIGATED
from alert_triage.triage.ports.alert_source import AlertSourceError
from alert_triage.triage.ports.ledger import TriageLedgerError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
CLEAN = "looked, nothing notable"


@dataclass(frozen=True)
class SuppliedConfig:
    """Configuration as a value: the port, with no source behind it."""

    scope: Scope = field(default_factory=lambda: Scope(owner="sre"))
    grouping: Grouping = field(default_factory=Grouping)
    ingestion: Ingestion = field(default_factory=Ingestion)
    re_notify: ReNotify = field(default_factory=ReNotify)
    ledger: Ledger = field(default_factory=Ledger)
    circuit_breakers: CircuitBreakers = field(default_factory=CircuitBreakers)
    investigation: Investigation = field(default_factory=Investigation)


@dataclass
class FakeAlertSource:
    """The alerts a run is handed, and the bound it asked for them from."""

    alerts: Sequence[Alert] = ()
    failure: str | None = None
    asked_since: datetime | None = None

    def fetch_since(self, since: datetime) -> Sequence[Alert]:
        """Answer with the alerts, remembering what bound was asked for."""
        self.asked_since = since
        if self.failure is not None:
            raise AlertSourceError(self.failure)
        return self.alerts


@dataclass
class FakeLedger:
    """The incidents on record, and the services it refuses to read or write."""

    on_record: Sequence[Incident] = ()
    unreadable: frozenset[str] = frozenset()
    unwritable: frozenset[str] = frozenset()
    journal: list[str] = field(default_factory=list)
    recorded: list[tuple[Incident, datetime]] = field(default_factory=list)

    def open_incidents(self, service: str, now: datetime) -> Sequence[Incident]:
        """Offer what is on record for the service, unless it is unreadable."""
        if service in self.unreadable:
            raise TriageLedgerError(f"the ledger is unreadable for {service}")
        return [incident for incident in self.on_record if incident.service == service]

    def record(self, incident: Incident, now: datetime) -> None:
        """Keep the incident, unless its service is one this ledger cannot write."""
        if incident.service in self.unwritable:
            raise TriageLedgerError(f"the ledger is unwritable for {incident.service}")
        self.journal.append(f"recorded {incident.service}")
        self.recorded.append((incident, now))

    @property
    def incidents(self) -> list[Incident]:
        """The incidents recorded, in the order the run recorded them."""
        return [incident for incident, _ in self.recorded]


@dataclass
class FakeNotifier:
    """The reports that got out, and the services no channel would accept."""

    undeliverable: frozenset[str] = frozenset()
    journal: list[str] = field(default_factory=list)
    delivered: list[TriageReport] = field(default_factory=list)

    def deliver(self, report: TriageReport) -> None:
        """Take the report, unless no channel would accept its service."""
        if report.service in self.undeliverable:
            raise NotifierError(f"no channel accepted the report for {report.service}")
        self.journal.append(f"delivered {report.service}")
        self.delivered.append(report)


@dataclass
class FakeInvestigator:
    """What an investigation came back with, and how often it was asked.

    ``outcomes`` is consumed one per call, so a test spells out a run-by-run
    arc — fail, fail, succeed — as the list it reads like.
    """

    outcomes: list[Diagnosis | InvestigatorError] = field(default_factory=list)
    asked: list[InvestigationTarget] = field(default_factory=list)

    def investigate(self, target: InvestigationTarget) -> Diagnosis:
        """Answer with the next outcome, remembering what it was asked about."""
        self.asked.append(target)
        outcome = self.outcomes.pop(0) if self.outcomes else _diagnosed(Findings())
        if isinstance(outcome, InvestigatorError):
            raise outcome
        return outcome


@pytest.fixture
def config() -> SuppliedConfig:
    """The documented defaults; a test varies one with ``dataclasses.replace``."""
    return SuppliedConfig()


def _alert(
    source_id: str, offset: timedelta = timedelta(), service: str = "checkout"
) -> Alert:
    return Alert(
        service=service,
        fired_at=NOON + offset,
        source_id=source_id,
        title=f"{service} alert {source_id}",
        link=f"https://platform/event/{source_id}",
    )


def _on_record(
    *alerts: Alert,
    incident_id: str = "incident-0",
    last_reported_at: datetime | None = NOON,
) -> Incident:
    return Incident(
        id=incident_id,
        service=alerts[0].service,
        alerts=alerts,
        last_reported_at=last_reported_at,
    )


def _ids() -> Callable[[], str]:
    """Deterministic identifiers, so a test can name the incident it expects."""
    counter = iter(range(1, 100))
    return lambda: f"incident-{next(counter)}"


def _build_report(incident: Incident, diagnosis: Diagnosis | None) -> TriageReport:
    """A builder standing in for the one the composition root injects."""
    return TriageReport(
        incident_id=incident.id,
        service=incident.service,
        subject=f"{incident.service}: {len(incident.alerts)} alert(s)",
        body=NOT_INVESTIGATED if diagnosis is None else diagnosis.account,
    )


def _run(
    source: FakeAlertSource,
    ledger: FakeLedger,
    notifier: FakeNotifier,
    config: Config,
    at: datetime = NOON,
    investigator: "FakeInvestigator | None" = None,
) -> RunOutcome:
    return run(
        source=source,
        ledger=ledger,
        notifier=notifier,
        investigator=investigator or FakeInvestigator(),
        build_report=_build_report,
        config=config,
        now=at,
        new_id=_ids(),
    )


def test_alerts_with_nothing_on_record_open_an_incident_and_report_it(
    config: SuppliedConfig,
) -> None:
    source = FakeAlertSource([_alert("a"), _alert("b", timedelta(minutes=5))])
    ledger = FakeLedger()
    notifier = FakeNotifier()

    outcome = _run(source, ledger, notifier, config)

    (recorded,) = ledger.incidents
    (report,) = notifier.delivered
    assert recorded.service == "checkout"
    assert [alert.source_id for alert in recorded.alerts] == ["a", "b"]
    assert report.incident_id == recorded.id
    assert outcome.groups == 1
    assert outcome.delivered == 1


def test_a_run_with_no_alerts_delivers_and_records_nothing_and_succeeds(
    config: SuppliedConfig,
) -> None:
    source = FakeAlertSource()
    ledger = FakeLedger()
    notifier = FakeNotifier()

    outcome = _run(source, ledger, notifier, config)

    assert ledger.recorded == []
    assert notifier.delivered == []
    assert outcome.groups == 0
    assert outcome.successful


def test_each_service_is_decided_and_reported_on_its_own(
    config: SuppliedConfig,
) -> None:
    quietened = _on_record(_alert("a", service="payments"), incident_id="payments-1")
    source = FakeAlertSource(
        [_alert("b"), _alert("c", timedelta(minutes=5), service="payments")]
    )
    ledger = FakeLedger([quietened])
    notifier = FakeNotifier()

    outcome = _run(source, ledger, notifier, config)

    assert {incident.service for incident in ledger.incidents} == {
        "checkout",
        "payments",
    }
    assert [report.service for report in notifier.delivered] == ["checkout"]
    assert outcome.groups == 2
    assert outcome.delivered == 1, "payments is inside its cooldown, checkout is new"


def test_a_run_fetches_from_its_instant_minus_the_configured_lookback(
    config: SuppliedConfig,
) -> None:
    source = FakeAlertSource()

    _run(source, FakeLedger(), FakeNotifier(), config)

    assert source.asked_since == NOON - config.ingestion.lookback


def test_a_wider_lookback_reaches_correspondingly_further_back(
    config: SuppliedConfig,
) -> None:
    widened = replace(config, ingestion=Ingestion(lookback_seconds=7200))
    source = FakeAlertSource()

    _run(source, FakeLedger(), FakeNotifier(), widened)

    assert source.asked_since == NOON - timedelta(hours=2)


def test_the_instant_a_run_is_given_reaches_the_fetch_and_the_records(
    config: SuppliedConfig,
) -> None:
    """One instant, so a slow run cannot decide against two different "now"s."""
    at = NOON + timedelta(hours=3)
    source = FakeAlertSource([_alert("a")])
    ledger = FakeLedger()

    _run(source, ledger, FakeNotifier(), config, at=at)

    (recorded_at,) = [at for _, at in ledger.recorded]
    assert source.asked_since == at - config.ingestion.lookback
    assert recorded_at == at


def test_a_delivered_report_is_recorded_as_reported_at_the_runs_instant(
    config: SuppliedConfig,
) -> None:
    """The stamp follows the delivery, so a cooldown only ever runs from one."""
    journal: list[str] = []
    ledger = FakeLedger(journal=journal)
    notifier = FakeNotifier(journal=journal)

    _run(FakeAlertSource([_alert("a")]), ledger, notifier, config)

    (recorded,) = ledger.incidents
    assert journal == ["delivered checkout", "recorded checkout"]
    assert recorded.last_reported_at == NOON


def test_a_failed_delivery_records_the_incident_without_a_new_stamp(
    config: SuppliedConfig,
) -> None:
    """The alerts still belong to the incident; the report is owed again."""
    on_record = _on_record(_alert("a"), last_reported_at=None)
    fresh = _alert("b", timedelta(minutes=5))
    ledger = FakeLedger([on_record])
    notifier = FakeNotifier(undeliverable=frozenset({"checkout"}))

    _run(FakeAlertSource([fresh]), ledger, notifier, config)

    (recorded,) = ledger.incidents
    assert notifier.delivered == []
    assert [alert.source_id for alert in recorded.alerts] == ["a", "b"]
    assert recorded.last_reported_at is None, "the next run owes this report"


def test_a_suppressed_report_delivers_nothing_and_keeps_the_previous_stamp(
    config: SuppliedConfig,
) -> None:
    quietened = _on_record(_alert("a"))
    ledger = FakeLedger([quietened])
    notifier = FakeNotifier()

    outcome = _run(
        FakeAlertSource([_alert("b", timedelta(minutes=5))]), ledger, notifier, config
    )

    (recorded,) = ledger.incidents
    assert notifier.delivered == []
    assert recorded.last_reported_at == NOON
    assert [alert.source_id for alert in recorded.alerts] == ["a", "b"]
    assert outcome.delivered == 0


def test_two_runs_over_the_same_inputs_reach_the_same_decisions(
    config: SuppliedConfig,
) -> None:
    alerts = [_alert("a"), _alert("b", timedelta(minutes=5), service="payments")]

    def once() -> tuple[RunOutcome, list[Incident], list[str]]:
        ledger = FakeLedger()
        notifier = FakeNotifier()
        outcome = _run(FakeAlertSource(alerts), ledger, notifier, config)
        return outcome, ledger.incidents, [r.subject for r in notifier.delivered]

    assert once() == once()


def _diagnosed(findings: Findings) -> Diagnosis:
    """What a completed investigation hands the run back."""
    return Diagnosis(
        headline="checkout: something happened",
        account="\n".join(one.observation for one in findings.findings) or CLEAN,
        hypothesis="an upstream dependency is slow" if findings.findings else None,
        confidence=Confidence.MEDIUM if findings.findings else None,
        findings=findings,
    )
