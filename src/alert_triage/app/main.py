"""The entrypoint: one run, started by a human or a scheduler, and an exit code.

Four things happen here and nowhere else. The run's instant is taken once, so
every decision below is made against the same "now". The environment is read
once, from the process and from any ``.env`` file beside it, so nothing below
resolves settings from two different pictures of the world — how much the run
says out loud is settled from that same environment, before it says anything.
Logging is configured once, so importing the pipeline into a test or a future
service configures nothing on its caller's behalf. And the run's outcome becomes
a process exit status, which is the only thing a scheduler can read.
"""

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
    """Perform one run and report how it went.

    Returns:
        ``SUCCESS`` when the run did everything it set out to do, and
        ``FAILURE`` when any stage failed or the deployment is unusable. A
        scheduler acts on this; a human reads the log.
    """
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
    """Account for what the run did, and turn that into a status."""
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
