import subprocess
from collections.abc import Callable

PackagedRun = Callable[..., subprocess.CompletedProcess[str]]

LEDGER_DIRECTORY = "/var/lib/alert-triage"


def _as_shell(run_image: PackagedRun, script: str) -> subprocess.CompletedProcess[str]:
    return run_image(entrypoint="/bin/sh", arguments=["-c", script])


def test_the_run_is_not_root(run_image: PackagedRun) -> None:
    result = _as_shell(run_image, "id -u")

    assert result.stdout.strip() != "0"


def test_the_run_can_write_where_its_ledger_belongs(run_image: PackagedRun) -> None:
    result = _as_shell(run_image, f"touch {LEDGER_DIRECTORY}/writable && echo ok")

    assert result.stdout.strip() == "ok"
