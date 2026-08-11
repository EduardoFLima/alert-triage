import pytest

from alert_triage.adapters.sqlite_ledger import (
    DEFAULT_LEDGER_PATH,
    LEDGER_PATH_VARIABLE,
    resolve_ledger_path,
)


def test_the_location_falls_back_to_the_documented_default() -> None:
    """A manual run needs no configuration: a path is not a credential."""
    assert resolve_ledger_path(env={}) == DEFAULT_LEDGER_PATH


def test_the_location_is_taken_from_the_environment_for_a_deployment() -> None:
    path = resolve_ledger_path(env={LEDGER_PATH_VARIABLE: "/var/lib/triage/ledger.db"})

    assert str(path) == "/var/lib/triage/ledger.db"


def test_the_environment_is_read_from_the_process_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LEDGER_PATH_VARIABLE, "/tmp/from-process.db")

    assert str(resolve_ledger_path()) == "/tmp/from-process.db"
