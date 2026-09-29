import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from alert_triage.configuration.port import Config
from alert_triage.configuration.settings import Scope
from alert_triage.investigation.contract import Diagnosis
from alert_triage.investigation.ports.investigator import (
    Investigator,
    InvestigatorError,
)
from alert_triage.notification.contract import TriageReport
from alert_triage.notification.ports.notifier import Notifier, NotifierError
from alert_triage.shared import journal
from alert_triage.triage.domain.grouping import AlertGroup, group_alerts
from alert_triage.triage.domain.incident import Incident
from alert_triage.triage.domain.policy import TriageDecision, triage
from alert_triage.triage.ports.alert_source import AlertSource, AlertSourceError
from alert_triage.triage.ports.ledger import TriageLedger, TriageLedgerError

_log = logging.getLogger(__name__)

ReportBuilder = Callable[[Incident, Diagnosis | None, str], TriageReport]
"""``None`` means no investigation completed, so the report is last resort."""


class Stage(StrEnum):
    FETCH = "fetching alerts"
    READ = "reading the ledger"
    INVESTIGATE = "investigating the incident"
    DELIVER = "delivering the report"
    RECORD = "recording the incident"


@dataclass(frozen=True)
class RunFailure:
    stage: Stage
    service: str
    detail: str

    def __str__(self) -> str:
        service = f" for {self.service}" if self.service else ""
        return f"{self.stage}{service}: {self.detail}"


@dataclass(frozen=True)
class RunOutcome:
    groups: int = 0
    delivered: int = 0
    failures: tuple[RunFailure, ...] = ()

    @property
    def successful(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class _Handled:
    delivered: bool = False
    failures: tuple[RunFailure, ...] = ()


def run(
    *,
    source: AlertSource,
    ledger: TriageLedger,
    notifier: Notifier,
    investigator: Investigator,
    build_report: ReportBuilder,
    config: Config,
    now: datetime,
    new_id: Callable[[], str],
) -> RunOutcome:
    """A failed fetch ends the run; later failures cost only their group."""
    try:
        fetched = source.fetch_since(now - config.ingestion.lookback)
    except AlertSourceError as error:
        _log.error(journal.banner("FETCH FAILED", detail=str(error)))
        return RunOutcome(failures=(RunFailure(Stage.FETCH, "", str(error)),))

    groups = group_alerts(fetched, config.grouping.window)
    _log.info(
        journal.event(
            "what fired, grouped into incidents",
            fetched=len(fetched),
            incidents=len(groups),
        )
    )

    handled = [
        _handle(
            group,
            ledger=ledger,
            notifier=notifier,
            investigator=investigator,
            build_report=build_report,
            config=config,
            now=now,
            new_id=new_id,
        )
        for group in groups
    ]
    return RunOutcome(
        groups=len(groups),
        delivered=sum(one.delivered for one in handled),
        failures=tuple(failure for one in handled for failure in one.failures),
    )


def _handle(
    group: AlertGroup,
    *,
    ledger: TriageLedger,
    notifier: Notifier,
    investigator: Investigator,
    build_report: ReportBuilder,
    config: Config,
    now: datetime,
    new_id: Callable[[], str],
) -> _Handled:
    """Port failures stay contained so later groups can still be reported."""
    _log.info(
        journal.banner(
            "INCIDENT",
            group.service,
            alerts=len(group.alerts),
            window=_spanned(group),
        )
    )

    try:
        known = ledger.open_incidents(group.service, now)
    except TriageLedgerError as error:
        _log.error(
            journal.event(
                "the ledger could not be read",
                service=group.service,
                detail=str(error),
            )
        )
        return _Handled(failures=(RunFailure(Stage.READ, group.service, str(error)),))

    decision = triage(
        group,
        known,
        now=now,
        window=config.grouping.window,
        cooldown=config.re_notify.cooldown,
        max_attempts=config.investigation.max_attempts,
        new_id=new_id,
    )

    _log.info(
        journal.event(
            f"what {group.service} is owed",
            investigation=(
                f"attempt {decision.incident.investigation_attempts + 1} of "
                f"{config.investigation.max_attempts}"
                if decision.should_investigate
                else "not owed one"
            ),
            report="due now" if decision.should_report else "inside its cooldown",
        )
    )

    diagnosis, investigation_failure = _investigated(
        decision, investigator=investigator, scope=config.scope
    )

    incident = (
        decision.incident.investigation_failed()
        if investigation_failure is not None
        else decision.incident
    )

    delivered, delivery_failure = _delivered(
        incident,
        diagnosis,
        should_report=decision.should_report,
        exhausted=incident.investigation_attempts >= config.investigation.max_attempts,
        notifier=notifier,
        build_report=build_report,
        env=config.scope.env,
    )

    if delivered:
        incident = incident.reported(now)

    record_failure = _recorded(incident, ledger, now)

    return _Handled(
        delivered=delivered,
        failures=tuple(
            failure
            for failure in (investigation_failure, delivery_failure, record_failure)
            if failure is not None
        ),
    )


def _investigated(
    decision: TriageDecision, *, investigator: Investigator, scope: Scope
) -> tuple[Diagnosis | None, RunFailure | None]:
    """A failed investigation costs an attempt, not the incident's place in the run."""
    incident = decision.incident
    if not decision.should_investigate:
        return None, None
    target = incident.investigation_target(scope)
    _log.info(
        journal.banner(
            "INVESTIGATING",
            incident.service,
            window=_between(target.window.start, target.window.end),
            alerts=target.alert_count,
            criticality="critical" if target.critical else None,
        )
    )
    try:
        diagnosis = investigator.investigate(target)
    except InvestigatorError as error:
        _log.error(
            journal.event(
                "the investigation failed",
                service=incident.service,
                detail=str(error),
            )
        )
        return None, RunFailure(Stage.INVESTIGATE, incident.service, str(error))
    return diagnosis, None


def _delivered(
    incident: Incident,
    diagnosis: Diagnosis | None,
    *,
    should_report: bool,
    exhausted: bool,
    notifier: Notifier,
    build_report: ReportBuilder,
    env: str,
) -> tuple[bool, RunFailure | None]:
    """Send failed investigations only once retries are spent.

    A failed delivery leaves the incident unstamped so the cooldown cannot start.
    """
    _log.info(journal.banner("REPORTING", incident.service))

    if not should_report:
        _log.info(
            journal.event(
                "nothing is delivered",
                because="the incident is inside its re-notify cooldown",
            )
        )
        return False, None
    if diagnosis is None and not exhausted:
        _log.info(
            journal.event(
                "nothing is delivered",
                because=(
                    "the investigation failed and this incident has attempts "
                    "left to spend on another"
                ),
            )
        )
        return False, None
    report = build_report(incident, diagnosis, env)
    try:
        notifier.deliver(report)
    except NotifierError as error:
        _log.error(
            journal.event(
                "the report was not delivered",
                service=incident.service,
                detail=str(error),
            )
        )
        return False, RunFailure(Stage.DELIVER, incident.service, str(error))
    _log.info(journal.event("delivered", incident=incident.id, subject=report.subject))
    return True, None


def _spanned(group: AlertGroup) -> str:
    return _between(group.alerts[0].fired_at, group.alerts[-1].fired_at)


def _between(start: datetime, end: datetime) -> str:
    return f"{start.isoformat()} → {end.isoformat()}"


def _recorded(
    incident: Incident, ledger: TriageLedger, now: datetime
) -> RunFailure | None:
    """Record undelivered incidents so the next run does not reopen their alerts."""
    try:
        ledger.record(incident, now)
    except TriageLedgerError as error:
        _log.error(
            journal.event(
                "the incident was not recorded",
                incident=incident.id,
                detail=str(error),
            )
        )
        return RunFailure(Stage.RECORD, incident.service, str(error))
    return None
