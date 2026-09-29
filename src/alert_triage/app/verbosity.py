"""Keep the run's account readable unless an operator asks for machinery."""

import logging
import sys
from collections.abc import Mapping

from alert_triage.investigation.adapters.adk.evidence import TOOL_CALL_LOGGER

LOG_LEVEL = "LOG_LEVEL"
LOG_TOOL_CALLBACK = "LOG_TOOL_CALLBACK"
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
"""Framework logger roots held quiet; both ADK spellings have existed."""

QUIET = logging.ERROR
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"

RECORD_SEPARATOR = "\n\n"
"""Handler-level spacing keeps tracebacks separated below the record."""


def configure_logging(env: Mapping[str, str]) -> int:
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
    """Unknown words are refused so a non-empty typo never means yes."""
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
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.terminator = RECORD_SEPARATOR
    return handler


def _asked_for_detail(level: int) -> bool:
    return level <= logging.DEBUG


def _level_named(named: str | None) -> int:
    """A bad level costs verbosity, never the run."""
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
