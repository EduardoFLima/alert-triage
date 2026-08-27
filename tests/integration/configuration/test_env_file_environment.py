from pathlib import Path

import pytest

from alert_triage.configuration.adapters.env_file import (
    DEFAULT_ENV_FILE,
    resolve_environment,
)


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(body)
    return path


def test_a_variable_the_file_sets_reaches_the_environment(tmp_path: Path) -> None:
    environment = resolve_environment(
        _write(tmp_path, "DD_API_KEY=from-the-file\n"), {}
    )

    assert environment["DD_API_KEY"] == "from-the-file"


def test_the_process_environment_wins_over_the_file(tmp_path: Path) -> None:
    """A .env file is a convenience for a laptop, never an override of a deployment."""
    path = _write(tmp_path, "SCOPE_OWNER=from-the-file\n")

    environment = resolve_environment(path, {"SCOPE_OWNER": "from-the-process"})

    assert environment["SCOPE_OWNER"] == "from-the-process"


def test_the_file_supplements_what_the_process_already_exported(tmp_path: Path) -> None:
    path = _write(tmp_path, "DD_APP_KEY=from-the-file\n")

    environment = resolve_environment(path, {"DD_API_KEY": "from-the-process"})

    assert environment["DD_API_KEY"] == "from-the-process"
    assert environment["DD_APP_KEY"] == "from-the-file"


def test_a_missing_env_file_is_not_an_error(tmp_path: Path) -> None:
    environment = resolve_environment(tmp_path / ".env", {"SCOPE_OWNER": "sre"})

    assert environment == {"SCOPE_OWNER": "sre"}


def test_comments_quotes_and_export_prefixes_are_understood(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
# The team whose alerts are triaged.
export SCOPE_OWNER=sre
ALERT_TRIAGE_EMAIL_TO="sre@example.com,oncall@example.com"
""",
    )

    environment = resolve_environment(path, {})

    assert environment["SCOPE_OWNER"] == "sre"
    assert environment["ALERT_TRIAGE_EMAIL_TO"] == "sre@example.com,oncall@example.com"


def test_a_name_the_file_leaves_unset_is_absent_rather_than_empty(
        tmp_path: Path,
) -> None:
    """An unset name must not shadow the same name exported by the process."""
    path = _write(tmp_path, "DD_SITE\n")

    environment = resolve_environment(path, {"DD_SITE": "datadoghq.eu"})

    assert environment["DD_SITE"] == "datadoghq.eu"


def test_the_environment_is_read_from_the_process_by_default(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCOPE_OWNER", "from-the-process")

    environment = resolve_environment(
        _write(tmp_path, "SOME_RANDOM_PROP=from-the-file\n")
    )

    assert environment["SCOPE_OWNER"] == "from-the-process"
    assert environment["SOME_RANDOM_PROP"] == "from-the-file"


def test_the_file_is_looked_for_beside_the_run_by_default() -> None:
    """Relative, so the file belongs to the checkout a run is started from."""
    assert DEFAULT_ENV_FILE.name == ".env"
    assert not DEFAULT_ENV_FILE.is_absolute()
