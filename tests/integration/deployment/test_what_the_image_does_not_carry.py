"""A build in a working checkout must not pick the developer's pockets.

A working checkout holds a real ``.env`` of credentials, a ``config.yaml``, and
a ``data/`` directory of run history, all beside the Dockerfile and all
gitignored — which is exactly the set a careless ``COPY . .`` bakes into an
image and hands to whoever runs it next. Being gitignored is no protection
here: a build context is not a commit.

The runtime stage is what these assert against, because that is what ships.
They were shown red against a Dockerfile with ``COPY . .`` appended, which
leaked ``.env.example`` and ``.git`` out of this worktree alone.
"""

import subprocess
from collections.abc import Callable

PackagedRun = Callable[..., subprocess.CompletedProcess[str]]

FORBIDDEN = (
    "/app/.env",
    "/app/.env.example",
    "/app/config.yaml",
    "/app/data",
    "/app/.git",
)
"""What a checkout holds that a distributed image has no business holding."""


def _listing(run_image: PackagedRun, path: str) -> subprocess.CompletedProcess[str]:
    """Ask the image whether a path exists, without starting a run."""
    return run_image(entrypoint="/bin/sh", arguments=["-c", f"ls -a {path}"])


def test_the_image_carries_no_credential_and_no_run_history(
    run_image: PackagedRun,
) -> None:
    """Every one of them, named individually so a failure says which leaked."""
    present = [path for path in FORBIDDEN if _listing(run_image, path).returncode == 0]

    assert present == []


DEVELOPMENT_TOOLING = ("pytest", "ruff", "mypy", "lint-imports")
"""The dev group's commands, which a distributed run has no use for."""


def test_the_image_carries_no_development_tooling(run_image: PackagedRun) -> None:
    """``--no-dev`` is the reason, and this is the check that it stayed there."""
    installed = [
        command
        for command in DEVELOPMENT_TOOLING
        if _listing(run_image, f"/app/.venv/bin/{command}").returncode == 0
    ]

    assert installed == []


def test_the_image_carries_no_source_tree(run_image: PackagedRun) -> None:
    """The package lives in the virtualenv, not in a directory beside it.

    ``--no-editable`` is what puts it there, and the absence of ``src/`` is what
    proves the install was not a link back to a directory the runtime stage
    never received.
    """
    assert _listing(run_image, "/app/src").returncode != 0
