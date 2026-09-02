"""The image is the run, and starting it with nothing is starting the run.

``test_installed_distribution`` establishes the same thing one layer in: that
the console script is wired to the entrypoint, proven by running it in a bare
environment and watching it refuse on the one setting that has no default.
This is that assertion from outside the container, where the bare environment
is not arranged but simply what a container starts with.
"""

import subprocess
from collections.abc import Callable

PackagedRun = Callable[..., subprocess.CompletedProcess[str]]


BROKEN_IMAGE = (
    "ModuleNotFoundError",
    "ImportError",
    "Permission denied",
    "command not found",
    "executable file not found",
)
"""How a badly built image fails, as opposed to how a run legitimately fails."""


def test_a_packaged_run_refuses_on_the_setting_that_has_no_default(
    run_image: PackagedRun,
) -> None:
    """Nothing of the host reaches the container, so scope is genuinely absent."""
    result = run_image()

    assert result.returncode != 0
    assert "scope.owner" in result.stderr


def test_a_configured_run_gets_all_the_way_to_the_platform(
    run_image: PackagedRun,
    configured_environment: dict[str, str],
    ledger_volume: str,
) -> None:
    """The test that catches a missing dependency or an unconstructible adapter.

    Reaching the fetch means configuration resolved, every adapter was built,
    and the ledger was opened — the whole of what the image is answerable for.
    What the run does about a platform it cannot reach is the run's business and
    is specified in ``triage-run``; that it *got there* is this one's.
    """
    result = run_image(
        environment=configured_environment,
        mounts={ledger_volume: "/var/lib/alert-triage"},
        network="none",
    )
    output = result.stdout + result.stderr

    assert [signature for signature in BROKEN_IMAGE if signature in output] == []
    assert result.returncode != 0
    assert "api.datadoghq.com" in output


def test_an_appended_argument_cannot_replace_the_job(
    container_runtime: str, image: str
) -> None:
    """Appending an argument must not turn the image into something else.

    A ``CMD`` is replaced by whatever an operator appends; an ``ENTRYPOINT`` is
    not. With no ``CMD`` at all there is nothing to replace, so the image cannot
    quietly stop being a triage run the first time someone passes it something.
    """
    declared = subprocess.run(
        [container_runtime, "inspect", "--format", "{{json .Config.Cmd}}", image],
        capture_output=True,
        text=True,
        timeout=30.0,
        check=True,
    )

    assert declared.stdout.strip() in {"null", "[]"}
