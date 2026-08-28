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
        "Domain and ports are free of vendor libraries",
    }
)
"""Every contract the architecture is held to, named here as well as in the file.

Stated twice on purpose. ``lint-imports`` exits zero over a ``.importlinter``
that declares nothing at all, so a truncated or badly merged file enforces
nothing and still reports success. Naming them here is what makes a contract
that goes missing fail a build rather than pass one, and it means adding a
context is a deliberate edit in two places rather than a silent drop in one.
"""


def _lint_imports() -> str:
    """Locate the ``lint-imports`` script, preferring the active environment."""
    venv_bin = str(Path(sys.executable).parent)
    executable = shutil.which("lint-imports", path=venv_bin) or shutil.which(
        "lint-imports"
    )
    if executable is None:
        pytest.fail("lint-imports is not installed; run `uv sync`")
    return executable


def _report() -> subprocess.CompletedProcess[str]:
    """Run every contract in ``.importlinter`` and hand back the whole report.

    ``NO_COLOR`` because the report is parsed, not read: import-linter colours
    the verdict even when its output is captured, and an escape sequence
    between the contract's name and ``KEPT`` is enough for the parse below to
    find nothing. A version that ignored the convention would leave this test
    failing loudly rather than passing silently, which is the direction this
    test exists to fail in.
    """
    return subprocess.run(
        [_lint_imports()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "NO_COLOR": "1"},
    )


def _contracts_that_ran(output: str) -> set[str]:
    """Names of the contracts the report accounted for, held or broken.

    A contract is listed as ``<name> KEPT`` or ``<name> BROKEN``; the detail
    that follows a failure repeats the name with no suffix, which is why only
    the suffixed lines count.
    """
    return {
        line.removesuffix(suffix).strip()
        for line in output.splitlines()
        for suffix in (" KEPT", " BROKEN")
        if line.endswith(suffix)
    }


def test_hexagonal_import_contracts_hold() -> None:
    """Dependencies point inward, and no context reaches past another's contract.

    The contracts live in ``.importlinter``; running them from a test means a
    boundary violation fails the same command as any other regression.
    """
    result = _report()

    assert result.returncode == 0, (
        "Import contract violated — the report below names the offending "
        f"module and import:\n\n{result.stdout}{result.stderr}"
    )


def test_no_architecture_contract_has_gone_missing() -> None:
    """A rule nobody runs is not a rule, and a silent one reports success.

    Separate from whether the contracts hold: a broken contract and a vanished
    contract need different fixes, and only this one catches the second.
    """
    ran = _contracts_that_ran(_report().stdout)

    assert ran == set(ENFORCED_CONTRACTS), (
        "The contracts run do not match the contracts this project is held to.\n"
        f"  missing from .importlinter: {sorted(ENFORCED_CONTRACTS - ran)}\n"
        f"  not named in this test:     {sorted(ran - ENFORCED_CONTRACTS)}"
    )
