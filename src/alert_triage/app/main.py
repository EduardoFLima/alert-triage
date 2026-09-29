import logging
from datetime import UTC, datetime

from alert_triage.app.composition import execute
from alert_triage.app.pipeline import RunOutcome
from alert_triage.app.verbosity import configure_logging
from alert_triage.configuration.adapters.env_file import resolve_environment
from alert_triage.configuration.port import ConfigError
from alert_triage.shared import journal

SUCCESS = 0
FAILURE = 1

_log = logging.getLogger(__name__)


def main() -> int:
    env = resolve_environment()
    level = configure_logging(env)
    now = datetime.now(UTC)
    _log.info(
        journal.banner(
            "TRIAGE RUN",
            started=now.isoformat(),
            detail=logging.getLevelName(level),
        )
    )
    try:
        outcome = execute(now=now, env=env)
    except ConfigError as error:
        _log.error(journal.banner("REFUSING TO START", reason=str(error)))
        return FAILURE
    return _reported(outcome)


def _reported(outcome: RunOutcome) -> int:
    _log.info(
        journal.banner(
            "RUN COMPLETE",
            groups=outcome.groups,
            delivered=outcome.delivered,
            failures=len(outcome.failures) or "none",
        )
    )
    for failure in outcome.failures:
        _log.error(
            journal.event(
                "a stage of the run failed",
                stage=failure.stage,
                service=failure.service or None,
                detail=failure.detail,
            )
        )
    return SUCCESS if outcome.successful else FAILURE
