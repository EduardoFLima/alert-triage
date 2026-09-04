"""One run: recent alerts, taken as far as a delivered report, and then out.

The pipeline depends on ports and the domain alone — it never learns which
platform answered, where the ledger keeps its records, or how many channels a
report went to. That is what makes a complete run exercisable with three
substitutes and no I/O at all, and it is why the wiring lives next door in
``composition``.

Nothing here reads a clock. The instant a run decides against is an argument,
taken once by the entrypoint, so the lookback bound, every cooldown decision,
and every recorded timestamp are the same "now".
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from alert_triage.configuration.port import Config
from alert_triage.configuration.settings import ScopedService, describing
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
from alert_triage.triage.domain.policy import (
    TriageDecision,
    triage,
    within_acceptable_latency,
)
from alert_triage.triage.ports.alert_source import AlertSource, AlertSourceError
from alert_triage.triage.ports.ledger import TriageLedger, TriageLedgerError

_log = logging.getLogger(__name__)

ReportBuilder = Callable[[Incident, Diagnosis | None], TriageReport]
"""How an incident and what was learned about it become the report.

``None`` means no investigation of the incident ever completed, which is the
only case the report of last resort is for. Deliberately a callable rather than
a port: a port earns its keep once report generation can fail in a way a caller
has to tell apart from the failures it already handles, and the builders this
run is handed cannot fail at all.
"""


class Stage(StrEnum):
    """The steps of a run, named so a failure says which one it happened in."""

    FETCH = "fetching alerts"
    READ = "reading the ledger"
    INVESTIGATE = "investigating the incident"
    DELIVER = "delivering the report"
    RECORD = "recording the incident"


@dataclass(frozen=True)
class RunFailure:
    """Something a run set out to do and could not.

    Attributes:
        stage: The step that failed.
        service: The service being handled, or empty for a failure that
            happened before there was one — a fetch concerns every service.
        detail: What the port said, for a human reading the run's account.
    """

    stage: Stage
    service: str
    detail: str

    def __str__(self) -> str:
        """Name the stage, the service, and what went wrong, in one line."""
        service = f" for {self.service}" if self.service else ""
        return f"{self.stage}{service}: {self.detail}"


@dataclass(frozen=True)
class RunOutcome:
    """What one run did, in the terms a scheduler and a human both read.

    Attributes:
        groups: How many same-incident groups the run handled.
        delivered: How many reports a channel accepted.
        failures: What the run could not do, in the order it happened.
    """

    groups: int = 0
    delivered: int = 0
    failures: tuple[RunFailure, ...] = ()

    @property
    def successful(self) -> bool:
        """Whether the run did everything it set out to do."""
        return not self.failures


@dataclass(frozen=True)
class _Handled:
    """What handling one group came to.

    Attributes:
        delivered: Whether a report about the group was delivered.
        failures: What handling the group could not do.
    """

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
    """Take the recent alerts as far as a delivered report, once.

    Args:
        source: Where the alerts to triage come from.
        ledger: What the system remembers between runs.
        notifier: Where a report is delivered.
        investigator: What looks into an incident before it is reported.
        build_report: How an incident and its findings become the report.
        config: The resolved settings the run is driven by.
        now: The instant this run decides against.
        new_id: Supplies the identifier a newly opened incident is named with.

    Returns:
        What the run handled, what it delivered, and what it could not do. A
        failure while handling one group leaves the others their reports; a
        failed fetch ends the run, because there is nothing to work on.
    """
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
    """Take one group from what is on record to a recorded incident.

    Only the port failures a group can suffer are caught, and each is contained
    here so the groups after this one still get their reports.
    """
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

    service = describing(config.scope.services, group.service)

    decision = triage(
        group,
        known,
        service=service,
        now=now,
        window=config.grouping.window,
        cooldown=config.re_notify.cooldown,
        max_attempts=config.investigation.max_attempts,
        new_id=new_id,
    )

    unowed = _why_nothing_is_owed(decision, service)

    _log.info(
        journal.event(
            f"what {group.service} is owed",
            investigation=(
                f"attempt {decision.incident.investigation_attempts + 1} of "
                f"{config.investigation.max_attempts}"
                if decision.should_investigate
                else "not owed one"
            ),
            report="due now" if decision.should_report else unowed,
        )
    )

    diagnosis, investigation_failure = _investigated(
        decision, investigator=investigator
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
        unowed=unowed,
        exhausted=incident.investigation_attempts >= config.investigation.max_attempts,
        notifier=notifier,
        build_report=build_report,
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
    decision: TriageDecision, *, investigator: Investigator
) -> tuple[Diagnosis | None, RunFailure | None]:
    """Investigate the incident if it is owed one, and say what came back.

    A failure here is reported but never fatal: it costs the incident an
    attempt and its findings, not its place in the run.
    """
    incident = decision.incident
    if not decision.should_investigate:
        return None, None
    target = incident.investigation_target
    _log.info(
        journal.banner(
            "INVESTIGATING",
            incident.service,
            window=_between(target.window.start, target.window.end),
            alerts=target.alert_count,
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


def _why_nothing_is_owed(decision: TriageDecision, service: ScopedService) -> str:
    """Which silence a run chose, in the words a reader needs to tell them apart.

    An incident nobody was ever owed a report about reads nothing like one that
    was reported yesterday, and a reader looking for the incident nobody
    examined must be able to tell it from the incident the run never saw.
    """
    if within_acceptable_latency(decision.incident, service):
        return (
            f"within {service.name}'s acceptable latency of "
            f"{service.acceptable_latency_ms}ms"
        )
    return "inside its cooldown"


def _delivered(
    incident: Incident,
    diagnosis: Diagnosis | None,
    *,
    should_report: bool,
    unowed: str,
    exhausted: bool,
    notifier: Notifier,
    build_report: ReportBuilder,
) -> tuple[bool, RunFailure | None]:
    """Deliver a report worth sending, and say whether a channel took it.

    A completed investigation is worth sending — including one that found
    nothing, which says the signals it consulted were examined and were clean. A failed
    investigation is not: "these alerts fired and we could not look at them"
    carries nothing a team can act on, so it
    waits for the retry. Once the attempts are spent that wait would be
    forever, so the alerts go out without findings rather than not at all.

    A report that did not get out leaves the incident unstamped, so the next
    run owes it again: a cooldown must never run from a report nobody received.
    """
    _log.info(journal.banner("REPORTING", incident.service))

    if not should_report:
        _log.info(
            journal.event("nothing is delivered", incident=incident.id, because=unowed)
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
    report = build_report(incident, diagnosis)
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
    """The stretch the group's alerts fired across, as a reader reads a window."""
    return _between(group.alerts[0].fired_at, group.alerts[-1].fired_at)


def _between(start: datetime, end: datetime) -> str:
    """One window, stated once and the same way wherever a run states one."""
    return f"{start.isoformat()} → {end.isoformat()}"


def _recorded(
    incident: Incident, ledger: TriageLedger, now: datetime
) -> RunFailure | None:
    """Record the incident, whether or not its report got out.

    The alerts belong to it either way: dropping them would leave the next run
    to re-derive a group this one has already seen, and possibly open a second
    incident for it.
    """
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
