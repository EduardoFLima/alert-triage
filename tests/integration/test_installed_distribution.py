import os
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pytest

import alert_triage

# Nothing of this machine's environment reaches the job, so the run refuses to
# start on the one setting that has no default — which is the cheapest proof
# that the command is wired to the entrypoint, and needs no integration.
BARE_ENVIRONMENT = {"PATH": os.environ.get("PATH", "")}


def test_package_is_installed_not_imported_from_the_working_directory() -> None:
    """The ``src/`` layout only pays off if tests import the installed package."""
    assert metadata.version("alert-triage")

    package_root = Path(alert_triage.__file__).parent
    assert package_root.name == "alert_triage"
    assert package_root.parent.name == "src"


def _console_script() -> str:
    """Locate the installed command, preferring the active environment."""
    venv_bin = str(Path(sys.executable).parent)
    executable = shutil.which("alert-triage", path=venv_bin) or shutil.which(
        "alert-triage"
    )
    if executable is None:
        pytest.fail("alert-triage is not installed; run `uv sync`")
    return executable


def _run(command: list[str], directory: Path) -> subprocess.CompletedProcess[str]:
    """Run the job as a scheduler would: its own process, its own environment."""
    return subprocess.run(
        command,
        cwd=directory,
        env=BARE_ENVIRONMENT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_console_script_is_installed_and_performs_a_run(tmp_path: Path) -> None:
    """One command, from the installation, with no path into the source tree."""
    result = _run([_console_script()], tmp_path)

    assert result.returncode != 0
    assert "scope.owner" in result.stderr


def test_the_module_entrypoint_is_the_same_job(tmp_path: Path) -> None:
    result = _run([sys.executable, "-m", "alert_triage"], tmp_path)

    assert result.returncode != 0
    assert "scope.owner" in result.stderr
