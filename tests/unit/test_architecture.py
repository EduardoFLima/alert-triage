import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

ENFORCED_CONTRACTS = frozenset(
    {
        "Triage's layers point inward",
        "Investigation's layers point inward",
        "Notification's layers point inward",
        "Configuration's layers point inward",
        "Contexts do not reach past each other's contracts",
        "The supporting contexts are independent of each other",
        "The shared kernel depends on no context",
        "The run takes adapters, it does not name them",
        "A declaration does not import the framework that runs it",
        "Domain and ports are free of vendor libraries",
    }
)
# import-linter exits zero with no contracts, so the names are asserted here too.


def _lint_imports() -> str:
    venv_bin = str(Path(sys.executable).parent)
    executable = shutil.which("lint-imports", path=venv_bin) or shutil.which(
        "lint-imports"
    )
    if executable is None:
        pytest.fail("lint-imports is not installed; run `uv sync`")
    return executable


def _report() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_lint_imports()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        # The parser below expects "<name> KEPT" with no ANSI escapes between them.
        env={**os.environ, "NO_COLOR": "1"},
    )


def _contracts_that_ran(output: str) -> set[str]:
    return {
        line.removesuffix(suffix).strip()
        for line in output.splitlines()
        for suffix in (" KEPT", " BROKEN")
        if line.endswith(suffix)
    }


def test_hexagonal_import_contracts_hold() -> None:
    result = _report()

    assert result.returncode == 0, (
        "Import contract violated — the report below names the offending "
        f"module and import:\n\n{result.stdout}{result.stderr}"
    )


def test_no_architecture_contract_has_gone_missing() -> None:
    ran = _contracts_that_ran(_report().stdout)

    assert ran == set(ENFORCED_CONTRACTS), (
        "The contracts run do not match the contracts this project is held to.\n"
        f"  missing from .importlinter: {sorted(ENFORCED_CONTRACTS - ran)}\n"
        f"  not named in this test:     {sorted(ran - ENFORCED_CONTRACTS)}"
    )
