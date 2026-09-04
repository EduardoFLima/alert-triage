"""What a run does when a stage fails: as little as possible, to one group.

A failed fetch ends the run, because there is nothing to work on. Anything
after it costs the group it happened to and leaves the others their
reports.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.app.pipeline import RunOutcome, Stage, run
from alert_triage.configuration.port import Config
from alert_triage.configuration.settings import (
    CircuitBreakers,
    CriticalService,
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
    critical_services: dict[str, CriticalService] = field(default_factory=dict)


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


def _ids() -> Callable[[], str]:
    """Deterministic identifiers, so a test can name the incident it expects."""
    counter = iter(range(1, 100))
    return lambda: f"incident-{next(counter)}"


def _build_report(
    incident: Incident, diagnosis: Diagnosis | None, service: ScopedService
) -> TriageReport:
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


def _three_services() -> list[Alert]:
    return [
        _alert("a"),
        _alert("b", timedelta(minutes=1), service="payments"),
        _alert("c", timedelta(minutes=2), service="search"),
    ]


def test_a_failed_fetch_ends_the_run_without_delivering_or_recording(
    config: SuppliedConfig,
) -> None:
    """A failed fetch is not a quiet period: there is nothing to work on."""
    ledger = FakeLedger()
    notifier = FakeNotifier()

    outcome = _run(FakeAlertSource(failure="Datadog is down"), ledger, notifier, config)

    assert ledger.recorded == []
    assert notifier.delivered == []
    assert not outcome.successful
    (failure,) = outcome.failures
    assert failure.stage == Stage.FETCH
    assert "Datadog is down" in failure.detail


def test_one_groups_failed_delivery_leaves_the_others_reported(
    config: SuppliedConfig,
) -> None:
    ledger = FakeLedger()
    notifier = FakeNotifier(undeliverable=frozenset({"payments"}))

    outcome = _run(FakeAlertSource(_three_services()), ledger, notifier, config)

    assert [report.service for report in notifier.delivered] == ["checkout", "search"]
    assert {incident.service for incident in ledger.incidents} == {
        "checkout",
        "payments",
        "search",
    }
    assert outcome.groups == 3
    assert outcome.delivered == 2
    assert not outcome.successful


def test_a_group_whose_ledger_read_fails_is_skipped_and_the_others_handled(
    config: SuppliedConfig,
) -> None:
    ledger = FakeLedger(unreadable=frozenset({"payments"}))
    notifier = FakeNotifier()

    outcome = _run(FakeAlertSource(_three_services()), ledger, notifier, config)

    assert [report.service for report in notifier.delivered] == ["checkout", "search"]
    assert [incident.service for incident in ledger.incidents] == [
        "checkout",
        "search",
    ]
    assert not outcome.successful


def test_a_group_whose_record_fails_costs_the_others_nothing(
    config: SuppliedConfig,
) -> None:
    ledger = FakeLedger(unwritable=frozenset({"payments"}))
    notifier = FakeNotifier()

    outcome = _run(FakeAlertSource(_three_services()), ledger, notifier, config)

    assert [incident.service for incident in ledger.incidents] == [
        "checkout",
        "search",
    ]
    assert outcome.delivered == 3, "the report got out before the record failed"
    assert not outcome.successful


def test_a_run_in_which_every_group_succeeds_finishes_successfully(
    config: SuppliedConfig,
) -> None:
    outcome = _run(
        FakeAlertSource(_three_services()), FakeLedger(), FakeNotifier(), config
    )

    assert outcome.failures == ()
    assert outcome.successful


def test_a_failure_names_the_stage_and_the_service_it_concerns(
    config: SuppliedConfig,
) -> None:
    """What a human needs to know from the outcome alone, without the logs."""
    ledger = FakeLedger(unreadable=frozenset({"search"}))
    notifier = FakeNotifier(undeliverable=frozenset({"payments"}))

    outcome = _run(FakeAlertSource(_three_services()), ledger, notifier, config)

    assert [(failure.stage, failure.service) for failure in outcome.failures] == [
        (Stage.DELIVER, "payments"),
        (Stage.READ, "search"),
    ]


def _diagnosed(findings: Findings) -> Diagnosis:
    """What a completed investigation hands the run back."""
    return Diagnosis(
        headline="checkout: something happened",
        account="\n".join(one.observation for one in findings.findings) or CLEAN,
        hypothesis="an upstream dependency is slow" if findings.findings else None,
        confidence=Confidence.MEDIUM if findings.findings else None,
        findings=findings,
    )
