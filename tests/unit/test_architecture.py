import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _lint_imports() -> str:
    """Locate the ``lint-imports`` script, preferring the active environment."""
    venv_bin = str(Path(sys.executable).parent)
    executable = shutil.which("lint-imports", path=venv_bin) or shutil.which(
        "lint-imports"
    )
    if executable is None:
        pytest.fail("lint-imports is not installed; run `uv sync`")
    return executable


def test_hexagonal_import_contracts_hold() -> None:
    """Dependencies point inward, and no vendor library reaches the core.

    The contracts live in ``pyproject.toml``; running them from a test means
    a boundary violation fails the same command as any other regression.
    """
    result = subprocess.run(
        [_lint_imports()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Import contract violated — the report below names the offending "
        f"module and import:\n\n{result.stdout}{result.stderr}"
    )
