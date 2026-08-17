import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alert_triage.adapters.sqlite_ledger.ledger import SqliteTriageLedger
from alert_triage.adapters.yaml_config.loader import ResolvedConfig, load_config
from alert_triage.app.run import RunOutcome, run
from alert_triage.domain.alert import Alert
from alert_triage.domain.findings import Finding, Findings, LogRecord, Signal
from alert_triage.domain.incident import Incident
from alert_triage.domain.report import TriageReport, build_report
from alert_triage.ports.investigator import InvestigatorError
from alert_triage.ports.notifier import NotifierError
from alert_triage.ports.triage_ledger import TriageLedger

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


@dataclass
class FakeAlertSource:
    """The platform, as far as a run can tell: whatever this run should fetch."""

    alerts: Sequence[Alert] = ()
    asked_since: datetime | None = None

    def fetch_since(self, since: datetime) -> Sequence[Alert]:
        """Answer with the alerts that fired at or after the bound."""
        self.asked_since = since
        return [alert for alert in self.alerts if alert.fired_at >= since]


@dataclass
class InMemoryLedger:
    """What the system remembers between runs, kept in a dictionary."""

    incidents: dict[str, Incident] = field(default_factory=dict)

    def open_incidents(self, service: str, now: datetime) -> Sequence[Incident]:
        """Offer the incidents on record for the service that are still open."""
        return [
            incident
            for incident in self.incidents.values()
            if incident.service == service and incident.closed_at is None
        ]

    def record(self, incident: Incident, now: datetime) -> None:
        """Keep this incident's state, replacing what was held before."""
        self.incidents[incident.id] = incident


@dataclass
class FakeNotifier:
    """A channel that takes reports, or refuses every one of them."""

    accepting: bool = True
    delivered: list[TriageReport] = field(default_factory=list)

    def deliver(self, report: TriageReport) -> None:
        """Take the report, unless this channel is refusing everything."""
        if not self.accepting:
            raise NotifierError("the relay refused the report")
        self.delivered.append(report)


@pytest.fixture
def config(tmp_path: Path) -> ResolvedConfig:
    """The documented defaults, resolved the way a deployment resolves them."""
    return load_config(tmp_path / "config.yaml", {"SCOPE_OWNER": "sre"})


@pytest.fixture
def new_id() -> Callable[[], str]:
    """Identifiers that stay unique across the runs of one test."""
    counter = iter(range(1, 100))
    return lambda: f"incident-{next(counter)}"


def _at(minutes: int) -> datetime:
    return NOON + timedelta(minutes=minutes)


def _alert(source_id: str, offset: timedelta = timedelta()) -> Alert:
    return Alert(
        service="checkout",
        fired_at=NOON + offset,
        source_id=source_id,
        title=f"Checkout alert {source_id}",
        link=f"https://platform/event/{source_id}",
    )


def _run(
    source: FakeAlertSource,
    ledger: TriageLedger,
    notifier: FakeNotifier,
    config: ResolvedConfig,
    new_id: Callable[[], str],
    at: datetime,
    investigator: "FakeInvestigator | None" = None,
) -> RunOutcome:
    return run(
        source=source,
        ledger=ledger,
        notifier=notifier,
        investigator=investigator or FakeInvestigator(),
        build_report=build_report,
        config=config,
        now=at,
        new_id=new_id,
    )


@dataclass
class FakeInvestigator:
    """The agent crew, standing in so no model or MCP server is involved."""

    outcomes: list[Findings | InvestigatorError] = field(default_factory=list)
    asked: list[Incident] = field(default_factory=list)

    def investigate(self, incident: Incident) -> Findings:
        """Answer with the next outcome, so a test spells out a run-by-run arc."""
        self.asked.append(incident)
        outcome = self.outcomes.pop(0) if self.outcomes else Findings()
        if isinstance(outcome, InvestigatorError):
            raise outcome
        return outcome


def _findings(observation: str = "checkout is timing out") -> Findings:
    return Findings(
        findings=(
            Finding(
                signal=Signal.LOGS,
                observation=observation,
                occurrences=3,
                examples=(
                    LogRecord(
                        timestamp=NOON,
                        level="ERROR",
                        message=observation,
                        service="checkout",
                    ),
                ),
            ),
        )
    )


def test_two_runs_open_an_incident_and_then_stay_quiet_about_it(
    config: ResolvedConfig, new_id: Callable[[], str]
) -> None:
    """The whole pipeline, twice: alerts in, one report out, then silence."""
    ledger = InMemoryLedger()
    notifier = FakeNotifier()
    source = FakeAlertSource([_alert("a"), _alert("b", timedelta(minutes=5))])

    first = _run(source, ledger, notifier, config, new_id, at=_at(6))

    source.alerts = [*source.alerts, _alert("c", timedelta(minutes=20))]
    second = _run(source, ledger, notifier, config, new_id, at=_at(21))

    (incident,) = ledger.incidents.values()
    (report,) = notifier.delivered
    assert first.delivered == 1
    assert second.delivered == 0, "the second run is well inside the cooldown"
    assert [alert.source_id for alert in incident.alerts] == ["a", "b", "c"]
    assert incident.last_reported_at == _at(6)
    assert report.subject.count("\n") == 0
    assert second.successful


def test_an_alert_in_two_overlapping_lookbacks_opens_one_incident(
    config: ResolvedConfig, new_id: Callable[[], str]
) -> None:
    """Runs overlap by design; the same alert twice is not a second problem."""
    ledger = InMemoryLedger()
    notifier = FakeNotifier()
    source = FakeAlertSource([_alert("a", timedelta(minutes=50))])

    _run(source, ledger, notifier, config, new_id, at=_at(60))
    second = _run(source, ledger, notifier, config, new_id, at=_at(90))

    (incident,) = ledger.incidents.values()
    assert source.asked_since == _at(30), "the lookbacks overlap"
    assert [alert.source_id for alert in incident.alerts] == ["a"]
    assert len(notifier.delivered) == 1
    assert second.delivered == 0


@contextmanager
def _on_disk_ledger(path: Path, config: ResolvedConfig) -> Iterator[TriageLedger]:
    """A ledger over its own connection, closed the way the run's caller closes it."""
    with closing(sqlite3.connect(path)) as connection:
        yield SqliteTriageLedger(
            connection,
            window=config.grouping.window,
            cooldown=config.re_notify.cooldown,
            retention=config.ledger.retention,
        )


def test_a_report_that_could_not_be_delivered_goes_out_on_the_next_run(
    tmp_path: Path, config: ResolvedConfig, new_id: Callable[[], str]
) -> None:
    """Across two connections to a real database, nothing is owed twice or lost."""
    database = tmp_path / "alert_triage.db"
    source = FakeAlertSource([_alert("a")])
    refusing = FakeNotifier(accepting=False)
    accepting = FakeNotifier()

    with _on_disk_ledger(database, config) as ledger:
        first = _run(source, ledger, refusing, config, new_id, at=_at(1))

    source.alerts = [*source.alerts, _alert("b", timedelta(minutes=5))]
    with _on_disk_ledger(database, config) as ledger:
        second = _run(source, ledger, accepting, config, new_id, at=_at(6))
        (recorded,) = ledger.open_incidents("checkout", _at(6))

    (report,) = accepting.delivered
    assert refusing.delivered == []
    assert not first.successful
    assert second.delivered == 1, "the report the first run owed"
    assert recorded.last_reported_at == _at(6)
    assert [alert.source_id for alert in report.incident.alerts] == ["a", "b"]
