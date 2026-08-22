"""The retry arc across real runs and a real ledger file.

The unit tests decide one run at a time. What these check is the thing no
single run can show: that the attempt an incident spends survives the process
that spent it, so silence is bounded and the report always eventually arrives.
"""

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alert_triage.adapters.sqlite_ledger.ledger import SqliteTriageLedger
from alert_triage.adapters.yaml_config.loader import ResolvedConfig, load_config
from alert_triage.app.run import RunOutcome, Stage, run
from alert_triage.domain.alert import Alert
from alert_triage.domain.findings import EvidenceItem, Finding, Findings, Signal
from alert_triage.domain.incident import Incident
from alert_triage.domain.report import TriageReport, build_report
from alert_triage.ports.investigator import InvestigatorError
from alert_triage.ports.triage_ledger import TriageLedger

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


@dataclass
class FakeAlertSource:
    alerts: Sequence[Alert] = ()

    def fetch_since(self, since: datetime) -> Sequence[Alert]:
        """Answer with the alerts still inside the run's lookback."""
        return [alert for alert in self.alerts if alert.fired_at >= since]


@dataclass
class FakeNotifier:
    delivered: list[TriageReport] = field(default_factory=list)

    def deliver(self, report: TriageReport) -> None:
        """Take the report, as a channel that accepted it would."""
        self.delivered.append(report)


@dataclass
class FakeInvestigator:
    """One outcome per run, so a test spells its arc out as a list."""

    outcomes: list[Findings | InvestigatorError] = field(default_factory=list)
    asked: list[Incident] = field(default_factory=list)

    def investigate(self, incident: Incident) -> Findings:
        """Answer with the next outcome in the arc this test spelled out."""
        self.asked.append(incident)
        outcome = self.outcomes.pop(0) if self.outcomes else Findings()
        if isinstance(outcome, InvestigatorError):
            raise outcome
        return outcome


@pytest.fixture
def config(tmp_path: Path) -> ResolvedConfig:
    return load_config(tmp_path / "config.yaml", {"SCOPE_OWNER": "sre"})


def _alert(source_id: str, minutes: int = 0) -> Alert:
    return Alert(
        service="checkout",
        fired_at=NOON + timedelta(minutes=minutes),
        source_id=source_id,
        title=f"Checkout alert {source_id}",
        link=f"https://platform/event/{source_id}",
    )


def _findings(observation: str) -> Findings:
    return Findings(
        findings=(
            Finding(
                signal=Signal.LOGS,
                observation=observation,
                occurrences=3,
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


@contextmanager
def _ledger(path: Path, config: ResolvedConfig) -> Iterator[TriageLedger]:
    with closing(sqlite3.connect(path)) as connection:
        yield SqliteTriageLedger(
            connection,
            window=config.grouping.window,
            cooldown=config.re_notify.cooldown,
            retention=config.ledger.retention,
        )


def _run(
    database: Path,
    config: ResolvedConfig,
    notifier: FakeNotifier,
    investigator: FakeInvestigator,
    at: datetime,
) -> RunOutcome:
    """One run in its own connection, as a scheduled process would be."""
    with _ledger(database, config) as ledger:
        return run(
            source=FakeAlertSource([_alert("a")]),
            ledger=ledger,
            notifier=notifier,
            investigator=investigator,
            build_report=build_report,
            config=config,
            now=at,
            new_id=lambda: "incident-1",
        )


def test_fail_fail_then_succeed_reports_only_once_and_only_at_the_end(
    tmp_path: Path, config: ResolvedConfig
) -> None:
    database = tmp_path / "alert_triage.db"
    notifier = FakeNotifier()
    investigator = FakeInvestigator(
        [
            InvestigatorError("the platform is down"),
            InvestigatorError("still down"),
            _findings("checkout is timing out upstream"),
        ]
    )

    first = _run(database, config, notifier, investigator, NOON)
    second = _run(
        database, config, notifier, investigator, NOON + timedelta(minutes=10)
    )
    third = _run(database, config, notifier, investigator, NOON + timedelta(minutes=20))

    assert not first.successful and first.delivered == 0
    assert not second.successful and second.delivered == 0
    assert third.successful and third.delivered == 1
    (report,) = notifier.delivered
    assert "checkout is timing out upstream" in report.body


def test_three_failures_end_in_the_alerts_going_out_without_findings(
    tmp_path: Path, config: ResolvedConfig
) -> None:
    """Alerts that fired are never lost to an unreachable platform."""
    database = tmp_path / "alert_triage.db"
    notifier = FakeNotifier()
    investigator = FakeInvestigator(
        [
            InvestigatorError("down"),
            InvestigatorError("down"),
            InvestigatorError("down"),
        ]
    )

    outcomes = [
        _run(
            database,
            config,
            notifier,
            investigator,
            NOON + timedelta(minutes=10 * attempt),
        )
        for attempt in range(3)
    ]

    assert [outcome.delivered for outcome in outcomes] == [0, 0, 1]
    (report,) = notifier.delivered
    assert "could not complete" in report.body
    assert "https://platform/event/a" in report.body
    assert all(not outcome.successful for outcome in outcomes)
    assert outcomes[2].failures[0].stage is Stage.INVESTIGATE


def test_a_fourth_run_neither_investigates_nor_reports_again(
    tmp_path: Path, config: ResolvedConfig
) -> None:
    """The cost of a broken platform stays bounded however long it stays broken."""
    database = tmp_path / "alert_triage.db"
    notifier = FakeNotifier()
    investigator = FakeInvestigator([InvestigatorError("down")] * 3)

    for attempt in range(3):
        _run(
            database,
            config,
            notifier,
            investigator,
            NOON + timedelta(minutes=10 * attempt),
        )
    asked_before = len(investigator.asked)

    fourth = _run(
        database, config, notifier, investigator, NOON + timedelta(minutes=30)
    )

    assert len(investigator.asked) == asked_before == 3
    assert len(notifier.delivered) == 1
    assert fourth.delivered == 0
    assert fourth.successful, "nothing was attempted, so nothing failed"


def test_the_attempts_spent_are_the_ones_read_back_from_the_ledger(
    tmp_path: Path, config: ResolvedConfig
) -> None:
    database = tmp_path / "alert_triage.db"
    investigator = FakeInvestigator([InvestigatorError("down")] * 2)

    _run(database, config, FakeNotifier(), investigator, NOON)
    _run(database, config, FakeNotifier(), investigator, NOON + timedelta(minutes=10))

    with _ledger(database, config) as ledger:
        (incident,) = ledger.open_incidents("checkout", NOON + timedelta(minutes=10))

    assert incident.investigation_attempts == 2


def test_a_successful_investigation_is_reported_on_the_first_run(
    tmp_path: Path, config: ResolvedConfig
) -> None:
    """Nothing about retrying delays the ordinary case."""
    database = tmp_path / "alert_triage.db"
    notifier = FakeNotifier()
    investigator = FakeInvestigator([_findings("checkout is timing out")])

    outcome = _run(database, config, notifier, investigator, NOON)

    assert outcome.delivered == 1
    assert outcome.successful
    with _ledger(database, config) as ledger:
        (incident,) = ledger.open_incidents("checkout", NOON)
    assert incident.investigation_attempts == 0


def _run_with_bound(
    database: Path, config: ResolvedConfig, notifier: FakeNotifier, at: datetime
) -> RunOutcome:
    return _run(
        database, config, notifier, FakeInvestigator([InvestigatorError("down")]), at
    )


def test_a_single_attempt_reports_without_findings_straight_away(
    tmp_path: Path, config: ResolvedConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operator who wants no retrying gets the old behavior back."""
    from dataclasses import replace as replace_dataclass

    from alert_triage.ports.config import Investigation

    bounded = replace_dataclass(config, investigation=Investigation(max_attempts=1))
    database = tmp_path / "alert_triage.db"
    notifier = FakeNotifier()

    outcome = _run_with_bound(database, bounded, notifier, NOON)

    assert outcome.delivered == 1
    (report,) = notifier.delivered
    assert "could not complete" in report.body
