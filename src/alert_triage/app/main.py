"""The entrypoint: one run, started by a human or a scheduler, and an exit code.

Four things happen here and nowhere else. The run's instant is taken once, so
every decision below is made against the same "now". The environment is read
once, from the process and from any ``.env`` file beside it, so nothing below
resolves settings from two different pictures of the world. Logging is
configured once, so importing the pipeline into a test or a future service
configures nothing on its caller's behalf. And the run's outcome becomes a
process exit status, which is the only thing a scheduler can read.
"""

import logging
import sys
from datetime import UTC, datetime

from alert_triage.adapters.env_file import resolve_environment
from alert_triage.app.composition import execute
from alert_triage.app.run import RunOutcome
from alert_triage.ports.config import ConfigError

SUCCESS = 0
FAILURE = 1

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"

_log = logging.getLogger(__name__)


def main() -> int:
    """Perform one run and report how it went.

    Returns:
        ``SUCCESS`` when the run did everything it set out to do, and
        ``FAILURE`` when any stage failed or the deployment is unusable. A
        scheduler acts on this; a human reads the log.
    """
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stderr)
    try:
        outcome = execute(now=datetime.now(UTC), env=resolve_environment())
    except ConfigError as error:
        _log.error("Refusing to start: %s", error)
        return FAILURE
    return _reported(outcome)


def _reported(outcome: RunOutcome) -> int:
    """Account for what the run did, and turn that into a status."""
    _log.info(
        "Handled %d group(s) and delivered %d report(s)",
        outcome.groups,
        outcome.delivered,
    )
    for failure in outcome.failures:
        _log.error("Failed %s", failure)
    if outcome.successful:
        return SUCCESS
    _log.error("Run finished with %d failure(s)", len(outcome.failures))
    return FAILURE
