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


def _listing(run_image: PackagedRun, path: str) -> subprocess.CompletedProcess[str]:
    return run_image(entrypoint="/bin/sh", arguments=["-c", f"ls -a {path}"])


def test_the_image_carries_no_credential_and_no_run_history(
    run_image: PackagedRun,
) -> None:
    present = [path for path in FORBIDDEN if _listing(run_image, path).returncode == 0]

    assert present == []


DEVELOPMENT_TOOLING = ("pytest", "ruff", "mypy", "lint-imports")


def test_the_image_carries_no_development_tooling(run_image: PackagedRun) -> None:
    installed = [
        command
        for command in DEVELOPMENT_TOOLING
        if _listing(run_image, f"/app/.venv/bin/{command}").returncode == 0
    ]

    assert installed == []


def test_the_image_carries_no_source_tree(run_image: PackagedRun) -> None:
    assert _listing(run_image, "/app/src").returncode != 0
