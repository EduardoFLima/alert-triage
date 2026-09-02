"""How much of a run reaches the log, decided once at the entrypoint.

A run has an account of its own to give: which specialists an incident was
worth asking, what each of them observed, and what the manager concluded from
them. Nothing else keeps that account, and it is written at ``INFO`` so that
reading it costs an operator nothing.

The frameworks underneath have accounts several times longer — every model
turn, every HTTP request a tool makes, every session the runner opens — and
they also write them at ``INFO``. Left alone, the run's own account is a few
lines in thousands. So they are held at ``ERROR``.

``ERROR`` rather than ``WARNING`` because a framework's warnings are about
itself, not about this run: an experimental feature flag being enabled, a
channel that is not mTLS. Neither says anything about the incident being
triaged, and both arrive on every run, which is what makes them noise rather
than news. What is left through is a framework saying it could not do the thing
it was asked to do.

Some of that talk never reaches a logger at all — ADK announces its
experimental features through Python's ``warnings``, which prints to stderr
past every level in this module. So warnings are routed into logging and held
with the frameworks that raise them, and one policy covers both.

One part of the run's own account is held the same way, and only one: the back
and forth between a specialist and the platform. What a specialist was asked and
what it concluded is the account; the queries it composed to get there are the
working, and they are the bulk of a run's output. ``LOG_TOOL_CALLBACK`` asks for
them.

Held rather than discarded. A reader who asks for ``DEBUG`` is asking about
the machinery, and gets all of it — the working included, flag or no flag.

One more thing is decided here, and it is decided here because only a handler
sees every record: each one is followed by a blank line. A block knows to leave
a line above itself, but a stack trace raised three libraries down knows
nothing, and an exception running straight into the block logged after it is how
a run's account stops being readable at exactly the moment it matters most.
"""

import logging
import sys
from collections.abc import Mapping

from alert_triage.investigation.adapters.adk.evidence import TOOL_CALL_LOGGER

LOG_LEVEL = "LOG_LEVEL"
"""The name an operator sets to be told more, or less. Read from ``.env`` too."""

LOG_TOOL_CALLBACK = "LOG_TOOL_CALLBACK"
"""The name an operator sets to be shown every tool call a specialist makes."""

_ASKED_FOR = frozenset({"1", "true", "yes", "on"})
_DECLINED = frozenset({"", "0", "false", "no", "off"})

DEFAULT_LEVEL = logging.INFO

FRAMEWORKS = (
    "py.warnings",
    "google",
    "google_adk",
    "google_genai",
    "httpx",
    "httpcore",
    "urllib3",
    "mcp",
    "asyncio",
    "datadog_api_client",
)
"""Whose account is not this run's.

``py.warnings`` is where ``logging.captureWarnings`` delivers everything raised
through Python's warnings machinery, which is how ADK announces an experimental
feature. Holding it here is what puts those on the same footing as the log lines
raised beside them.

Both spellings of ADK's own logger are named because the library has used each,
and a name that logs nothing costs nothing to hold. Naming a package holds every
logger beneath it, which is what covers the one a session manager opens three
modules deep.
"""

QUIET = logging.ERROR
"""Where a framework is held while the run is the thing being read.

High enough to cover a framework's warnings about itself, which are the ones it
raises on every run whatever is happening. Not high enough to cover a framework
saying it could not do what it was asked.
"""

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"

RECORD_SEPARATOR = "\n\n"
"""What follows every record: its own newline, and a blank line after it.

The handler's terminator rather than the formatter's output, because a
formatter appends a traceback *after* the string it built — a newline added
there lands above the stack trace rather than below it, which is precisely
backwards for the record that needs the separation most.
"""


def configure_logging(env: Mapping[str, str]) -> int:
    """Decide how much a run says, and say it in one place for the whole process.

    Args:
        env: The environment the deployment is configured from, which is where
            an operator names a level.

    Returns:
        The level the run was configured at, so the entrypoint can say so.
    """
    level = _level_named(env.get(LOG_LEVEL))
    logging.basicConfig(level=level, handlers=[_handler()])
    logging.captureWarnings(True)
    logging.getLogger().setLevel(level)
    held = level if _asked_for_detail(level) else QUIET
    for framework in FRAMEWORKS:
        logging.getLogger(framework).setLevel(held)
    logging.getLogger(TOOL_CALL_LOGGER).setLevel(
        level
        if _asked_for_detail(level) or _wanted(env.get(LOG_TOOL_CALLBACK))
        else QUIET
    )
    return level


def _wanted(said: str | None) -> bool:
    """Whether a deployment asked for the working as well as the account.

    Absent is no, which is the reading a deployment gets by saying nothing. A
    word outside the declared set is refused rather than guessed at: reading
    ``LOG_TOOL_CALLBACK=disabled`` as a yes because it is not empty is the trap
    this exists to avoid.
    """
    if said is None:
        return False
    named = said.strip().lower()
    if named in _ASKED_FOR:
        return True
    if named not in _DECLINED:
        logging.getLogger(__name__).warning(
            "%s=%r is neither a yes nor a no, so the tool calls stay out of this "
            "run's account. A yes is one of: %s",
            LOG_TOOL_CALLBACK,
            said,
            ", ".join(sorted(_ASKED_FOR)),
        )
    return False


def _handler() -> logging.Handler:
    """Where a run's account is written, and how each record is closed off."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.terminator = RECORD_SEPARATOR
    return handler


def _asked_for_detail(level: int) -> bool:
    """Whether the reader asked about the machinery rather than about the run."""
    return level <= logging.DEBUG


def _level_named(named: str | None) -> int:
    """The level an operator asked for, however they typed it.

    A name nobody declared is refused rather than guessed at, and the run
    starts anyway: a typo in an environment must cost a deployment its
    verbosity, never its triage.
    """
    if not named:
        return DEFAULT_LEVEL
    level = logging.getLevelNamesMapping().get(named.strip().upper())
    if level is None:
        logging.getLogger(__name__).warning(
            "%s=%r names no level anybody declared, so this run accounts for "
            "itself at %s. The levels are: %s",
            LOG_LEVEL,
            named,
            logging.getLevelName(DEFAULT_LEVEL),
            ", ".join(logging.getLevelNamesMapping()),
        )
        return DEFAULT_LEVEL
    return level
