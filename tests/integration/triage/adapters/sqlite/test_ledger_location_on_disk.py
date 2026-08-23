from pathlib import Path

import pytest

from alert_triage.triage.adapters.sqlite import (
    DEFAULT_LEDGER_PATH,
    LEDGER_PATH_VARIABLE,
    resolve_ledger_path,
)


@pytest.fixture(autouse=True)
def working_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Resolving makes a directory, and none of them belong in the checkout."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_the_location_falls_back_to_the_documented_default() -> None:
    """A manual run needs no configuration: a path is not a credential."""
    assert resolve_ledger_path(env={}) == DEFAULT_LEDGER_PATH


def test_the_location_is_taken_from_the_environment_for_a_deployment(
    working_directory: Path,
) -> None:
    deployment = working_directory / "var" / "lib" / "triage" / "ledger.db"

    resolved = resolve_ledger_path(env={LEDGER_PATH_VARIABLE: str(deployment)})

    assert resolved == deployment


def test_the_environment_is_read_from_the_process_by_default(
    monkeypatch: pytest.MonkeyPatch, working_directory: Path
) -> None:
    monkeypatch.setenv(LEDGER_PATH_VARIABLE, str(working_directory / "from-process.db"))

    assert resolve_ledger_path() == working_directory / "from-process.db"


def test_resolving_makes_the_directory_the_database_will_sit_in(
    working_directory: Path,
) -> None:
    """SQLite creates the database file on first use but never the folder."""
    resolve_ledger_path(env={})

    assert (working_directory / DEFAULT_LEDGER_PATH.parent).is_dir()


def test_a_directory_already_there_is_left_alone(working_directory: Path) -> None:
    """Every run resolves the location; only the first one has work to do."""
    resolve_ledger_path(env={})
    kept = working_directory / DEFAULT_LEDGER_PATH.parent / "from-an-earlier-run.db"
    kept.touch()

    resolve_ledger_path(env={})

    assert kept.is_file()
