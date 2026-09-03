"""A job that reads alerts and sends reports needs no privilege to do it.

Root is the default a container gets for free, and the cost of not noticing is
paid by whoever mounts a host directory into it. The fixed UID matters as much
as the non-rootness: a named volume is initialised with the image's ownership,
so the run can write its ledger with no host-side permission work.
"""

import subprocess
from collections.abc import Callable

PackagedRun = Callable[..., subprocess.CompletedProcess[str]]

LEDGER_DIRECTORY = "/var/lib/alert-triage"


def _as_shell(run_image: PackagedRun, script: str) -> subprocess.CompletedProcess[str]:
    """Ask the image about itself, without starting a run."""
    return run_image(entrypoint="/bin/sh", arguments=["-c", script])


def test_the_run_is_not_root(run_image: PackagedRun) -> None:
    result = _as_shell(run_image, "id -u")

    assert result.stdout.strip() != "0"


def test_the_run_can_write_where_its_ledger_belongs(run_image: PackagedRun) -> None:
    """Non-root is only half of it: the user must own the directory it needs."""
    result = _as_shell(run_image, f"touch {LEDGER_DIRECTORY}/writable && echo ok")

    assert result.stdout.strip() == "ok"
