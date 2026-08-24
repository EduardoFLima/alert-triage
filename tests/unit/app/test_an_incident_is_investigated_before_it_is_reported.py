"""The investigation arc across runs: attempts spent, retried, exhausted.

A failed investigation costs an attempt and delivers nothing, a retry that
succeeds clears them, and the last attempt failing still gets the alerts
out — as the report of last resort it is.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
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
)
from alert_triage.investigation.contract import (
    EvidenceItem,
    Finding,
    Findings,
    InvestigationTarget,
    Signal,
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

    outcomes: list[Findings | InvestigatorError] = field(default_factory=list)
    asked: list[InvestigationTarget] = field(default_factory=list)

    def investigate(self, target: InvestigationTarget) -> Findings:
        """Answer with the next outcome, remembering what it was asked about."""
        self.asked.append(target)
        outcome = self.outcomes.pop(0) if self.outcomes else Findings()
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


def _findings(observation: str = "OOMKilled recurs") -> Findings:
    return Findings(
        findings=(
            Finding(
                signal=Signal.LOGS,
                observation=observation,
                occurrences=1,
                examples=(
                    EvidenceItem(
                        id="call-1/item-1",
                        instant=NOON,
                        summary=observation,
                        payload={"message": observation},
                    ),
                ),
            ),
        )
    )


def _ids() -> Callable[[], str]:
    """Deterministic identifiers, so a test can name the incident it expects."""
    counter = iter(range(1, 100))
    return lambda: f"incident-{next(counter)}"


def _build_report(incident: Incident, findings: Findings | None) -> TriageReport:
    """A builder standing in for the one the composition root injects."""
    return TriageReport(
        incident_id=incident.id,
        service=incident.service,
        subject=f"{incident.service}: {len(incident.alerts)} alert(s)",
        body=NOT_INVESTIGATED if findings is None else _found(findings),
    )


def _found(findings: Findings) -> str:
    """What a report built from findings says, in as little as a test needs."""
    return "\n".join(finding.observation for finding in findings.findings) or CLEAN


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


def test_a_due_incident_is_investigated_and_its_findings_reported(
    config: SuppliedConfig,
) -> None:
    source = FakeAlertSource([_alert("a")])
    notifier = FakeNotifier()
    investigator = FakeInvestigator([_findings("OOMKilled recurs")])

    _run(source, FakeLedger(), notifier, config, investigator=investigator)

    assert len(investigator.asked) == 1
    (report,) = notifier.delivered
    assert "OOMKilled recurs" in report.body


def test_an_incident_inside_its_cooldown_is_never_investigated(
    config: SuppliedConfig,
) -> None:
    """A suppressed report costs no model spend."""
    quietened = _on_record(_alert("a"))
    source = FakeAlertSource([_alert("b", timedelta(minutes=5))])
    investigator = FakeInvestigator()

    _run(
        source,
        FakeLedger([quietened]),
        FakeNotifier(),
        config,
        investigator=investigator,
    )

    assert investigator.asked == []


def test_a_failed_investigation_delivers_nothing_and_spends_an_attempt(
    config: SuppliedConfig,
) -> None:
    source = FakeAlertSource([_alert("a")])
    ledger = FakeLedger()
    notifier = FakeNotifier()
    investigator = FakeInvestigator([InvestigatorError("the platform is down")])

    outcome = _run(source, ledger, notifier, config, investigator=investigator)

    assert notifier.delivered == []
    (recorded,) = ledger.incidents
    assert recorded.investigation_attempts == 1
    assert recorded.last_reported_at is None
    assert not outcome.successful
    assert outcome.failures[0].stage is Stage.INVESTIGATE
    assert outcome.failures[0].service == "checkout"


def test_a_retry_that_fails_again_still_delivers_nothing(
    config: SuppliedConfig,
) -> None:
    already = replace(
        _on_record(_alert("a"), last_reported_at=None), investigation_attempts=1
    )
    source = FakeAlertSource([_alert("b", timedelta(minutes=5))])
    ledger = FakeLedger([already])
    notifier = FakeNotifier()
    investigator = FakeInvestigator([InvestigatorError("still down")])

    outcome = _run(source, ledger, notifier, config, investigator=investigator)

    assert notifier.delivered == []
    assert ledger.incidents[0].investigation_attempts == 2
    assert not outcome.successful


def test_a_retry_that_succeeds_reports_and_clears_the_attempts(
    config: SuppliedConfig,
) -> None:
    already = replace(
        _on_record(_alert("a"), last_reported_at=None), investigation_attempts=2
    )
    source = FakeAlertSource([_alert("b", timedelta(minutes=5))])
    ledger = FakeLedger([already])
    notifier = FakeNotifier()
    investigator = FakeInvestigator([_findings("found it")])

    outcome = _run(source, ledger, notifier, config, investigator=investigator)

    (report,) = notifier.delivered
    assert "found it" in report.body
    assert ledger.incidents[0].investigation_attempts == 0
    assert ledger.incidents[0].last_reported_at == NOON
    assert outcome.successful


def test_a_successful_investigation_whose_delivery_fails_keeps_its_attempts(
    config: SuppliedConfig,
) -> None:
    """Clearing the counter here would strand findings nobody received."""
    already = replace(
        _on_record(_alert("a"), last_reported_at=None), investigation_attempts=2
    )
    source = FakeAlertSource([_alert("b", timedelta(minutes=5))])
    ledger = FakeLedger([already])
    notifier = FakeNotifier(undeliverable=frozenset({"checkout"}))
    investigator = FakeInvestigator([_findings("found it")])

    _run(source, ledger, notifier, config, investigator=investigator)

    assert ledger.incidents[0].investigation_attempts == 2
    assert ledger.incidents[0].last_reported_at is None


def test_an_investigation_that_found_nothing_notable_is_still_delivered(
    config: SuppliedConfig,
) -> None:
    """'We looked and it is clean' is a result, not a failure."""
    source = FakeAlertSource([_alert("a")])
    notifier = FakeNotifier()
    investigator = FakeInvestigator([Findings()])

    outcome = _run(source, FakeLedger(), notifier, config, investigator=investigator)

    (report,) = notifier.delivered
    assert report.body == CLEAN
    assert outcome.successful


def test_the_last_attempt_failing_delivers_the_alerts_without_findings(
    config: SuppliedConfig,
) -> None:
    already = replace(
        _on_record(_alert("a"), last_reported_at=None), investigation_attempts=2
    )
    source = FakeAlertSource([_alert("b", timedelta(minutes=5))])
    ledger = FakeLedger([already])
    notifier = FakeNotifier()
    investigator = FakeInvestigator([InvestigatorError("still down")])

    outcome = _run(source, ledger, notifier, config, investigator=investigator)

    (report,) = notifier.delivered
    assert report.body == NOT_INVESTIGATED
    assert ledger.incidents[0].last_reported_at == NOON
    assert ledger.incidents[0].investigation_attempts == 0
    assert not outcome.successful, "the investigation still failed"


def test_an_incident_with_attempts_spent_is_not_investigated_again(
    config: SuppliedConfig,
) -> None:
    """A failed delivery is retried without spending another investigation."""
    spent = replace(
        _on_record(_alert("a"), last_reported_at=None), investigation_attempts=3
    )
    source = FakeAlertSource([_alert("b", timedelta(minutes=5))])
    ledger = FakeLedger([spent])
    notifier = FakeNotifier()
    investigator = FakeInvestigator()

    _run(source, ledger, notifier, config, investigator=investigator)

    assert investigator.asked == []
    (report,) = notifier.delivered
    assert report.body == NOT_INVESTIGATED


def test_one_groups_investigation_failure_leaves_the_others_their_reports(
    config: SuppliedConfig,
) -> None:
    source = FakeAlertSource(
        [_alert("a"), _alert("b", service="payments"), _alert("c", service="search")]
    )
    notifier = FakeNotifier()
    investigator = FakeInvestigator(
        [_findings("first"), InvestigatorError("down"), _findings("third")]
    )

    outcome = _run(source, FakeLedger(), notifier, config, investigator=investigator)

    assert len(notifier.delivered) == 2
    assert outcome.delivered == 2
    assert not outcome.successful
