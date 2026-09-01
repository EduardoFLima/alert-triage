"""What a run says out loud, and what it keeps for whoever asks for detail.

A run's own account — which specialist was asked, what it observed, what the
manager concluded from it — is the log. The frameworks underneath it have an
account of their own, several times longer, and reading one in the other is
how the account nobody else keeps gets lost. So the frameworks are quiet
unless a reader asks for them by name — their warnings included, whether they
arrive as log records or through Python's own warnings machinery.
"""

import logging
import sys
import warnings
from collections.abc import Iterator

import pytest

from alert_triage.app import verbosity

_RUN = "alert_triage.app.pipeline"


@pytest.fixture(autouse=True)
def _restored_levels() -> Iterator[None]:
    """Leave the process's logging exactly as this test found it."""
    named = ("", _RUN, *verbosity.FRAMEWORKS)
    before = {name: logging.getLogger(name).level for name in named}
    handlers = logging.getLogger().handlers[:]
    yield
    logging.captureWarnings(False)
    logging.getLogger().handlers[:] = handlers
    for name, level in before.items():
        logging.getLogger(name).setLevel(level)


def test_a_run_nobody_asked_for_detail_from_accounts_for_itself() -> None:
    verbosity.configure_logging({})

    assert logging.getLogger(_RUN).isEnabledFor(logging.INFO)


def test_the_frameworks_are_quiet_while_the_run_speaks() -> None:
    verbosity.configure_logging({})

    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
    assert not logging.getLogger("google_adk").isEnabledFor(logging.INFO)


def test_every_record_is_followed_by_a_blank_line() -> None:
    """A traceback runs into whatever is logged next unless something separates them.

    Owned here rather than by whatever composed the message, because only a
    handler sees every record: a block knows to leave a line after itself, and a
    stack trace raised three libraries down knows nothing at all.
    """
    root = logging.getLogger()
    root.handlers.clear()

    verbosity.configure_logging({})

    (handler,) = root.handlers
    assert isinstance(handler, logging.StreamHandler)
    assert handler.terminator == "\n\n"


def test_the_records_are_written_where_a_run_writes_everything_else() -> None:
    root = logging.getLogger()
    root.handlers.clear()

    verbosity.configure_logging({})

    (handler,) = root.handlers
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stderr
    assert handler.formatter is not None


def test_a_frameworks_warning_about_itself_is_not_the_runs_business() -> None:
    """An experimental feature flag, or a channel that is not mTLS: machinery talk."""
    mcp = logging.getLogger("google_adk.google.adk.tools.mcp_tool.mcp_session_manager")

    verbosity.configure_logging({})

    assert not mcp.isEnabledFor(logging.WARNING)


def test_a_framework_that_is_actually_broken_is_never_silenced() -> None:
    verbosity.configure_logging({})

    assert logging.getLogger("httpx").isEnabledFor(logging.ERROR)


def test_a_python_warning_is_held_exactly_as_a_framework_log_line_is(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ADK announces its experimental features this way, not through a logger."""
    with caplog.at_level(logging.INFO):
        verbosity.configure_logging({})
        warnings.showwarning(
            UserWarning("[EXPERIMENTAL] feature PLUGGABLE_AUTH is enabled"),
            UserWarning,
            "google/adk/features/_feature_decorator.py",
            72,
        )

    assert caplog.text == ""


def test_a_reader_who_asks_for_detail_is_given_the_python_warnings_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        verbosity.configure_logging({"LOG_LEVEL": "DEBUG"})
        warnings.showwarning(
            UserWarning("[EXPERIMENTAL] feature PLUGGABLE_AUTH is enabled"),
            UserWarning,
            "google/adk/features/_feature_decorator.py",
            72,
        )

    assert "PLUGGABLE_AUTH" in caplog.text


def test_a_reader_who_asks_for_detail_is_given_the_frameworks_too() -> None:
    verbosity.configure_logging({"LOG_LEVEL": "DEBUG"})

    assert logging.getLogger("httpx").isEnabledFor(logging.DEBUG)
    assert logging.getLogger("google_adk").isEnabledFor(logging.DEBUG)


def test_the_level_is_named_however_an_operator_happens_to_type_it() -> None:
    verbosity.configure_logging({"LOG_LEVEL": "debug"})

    assert logging.getLogger(_RUN).isEnabledFor(logging.DEBUG)


def test_a_run_told_to_say_less_says_less() -> None:
    verbosity.configure_logging({"LOG_LEVEL": "WARNING"})

    assert not logging.getLogger(_RUN).isEnabledFor(logging.INFO)


def test_a_level_nobody_declared_is_refused_out_loud_and_the_run_still_starts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A typo in a deployment's environment must not cost it its account."""
    with caplog.at_level(logging.WARNING):
        level = verbosity.configure_logging({"LOG_LEVEL": "chatty"})

    assert "chatty" in caplog.text
    assert level == logging.INFO
