from pathlib import Path

from alert_triage.triage.adapters.sqlite import DEFAULT_LEDGER_PATH


def test_the_default_puts_the_database_under_a_directory_of_its_own() -> None:
    """A run from a checkout drops its database in `data/`, not next to the code."""
    assert Path("data/alert_triage.db") == DEFAULT_LEDGER_PATH
