import os
import shutil
import subprocess
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from uuid import uuid4

import pytest

IMAGE_VARIABLE = "ALERT_TRIAGE_IMAGE"
DEFAULT_IMAGE = "alert-triage:test"
LEDGER_DIRECTORY = "/var/lib/alert-triage"
DAEMON_TIMEOUT_SECONDS = 30.0
BUILD_TIMEOUT_SECONDS = 900.0
RUN_TIMEOUT_SECONDS = 180.0


@pytest.fixture(scope="session")
def container_runtime() -> str:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("no container runtime: docker is not on the PATH")
    answered = subprocess.run(
        [docker, "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        text=True,
        timeout=DAEMON_TIMEOUT_SECONDS,
        check=False,
    )
    if answered.returncode != 0:
        pytest.skip(
            "no container runtime: docker is installed but the daemon did not answer"
        )
    return docker


@pytest.fixture(scope="session")
def image(container_runtime: str, repository_root: Path) -> str:
    supplied = os.environ.get(IMAGE_VARIABLE)
    if supplied:
        return supplied
    built = subprocess.run(
        [container_runtime, "build", "--tag", DEFAULT_IMAGE, str(repository_root)],
        capture_output=True,
        text=True,
        timeout=BUILD_TIMEOUT_SECONDS,
        check=False,
    )
    if built.returncode != 0:
        pytest.fail(f"the image did not build:\n{built.stdout}\n{built.stderr}")
    return DEFAULT_IMAGE


@pytest.fixture
def configured_environment() -> dict[str, str]:
    return {
        "SCOPE_OWNER": "sre",
        "DD_API_KEY": "not-a-real-key",
        "DD_APP_KEY": "not-a-real-key",
        "DD_SITE": "datadoghq.com",
        "GOOGLE_API_KEY": "not-a-real-key",
        "ALERT_TRIAGE_TEAMS_WEBHOOK_URL": "https://example.com/webhook",
        "INGESTION_MAX_RETRIES": "0",
        "INGESTION_REQUEST_TIMEOUT_SECONDS": "5",
    }


@pytest.fixture(scope="session")
def compose_command(container_runtime: str) -> list[str]:
    subcommand = [container_runtime, "compose"]
    if _answers(subcommand):
        return subcommand
    standalone = shutil.which("docker-compose")
    if standalone is not None and _answers([standalone]):
        return [standalone]
    pytest.skip("no compose: neither `docker compose` nor `docker-compose` answered")


def _answers(command: list[str]) -> bool:
    try:
        answered = subprocess.run(
            [*command, "version"],
            capture_output=True,
            text=True,
            timeout=DAEMON_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return answered.returncode == 0


@pytest.fixture
def ledger_volume(container_runtime: str) -> Iterator[str]:
    name = f"alert-triage-test-{uuid4().hex[:12]}"
    subprocess.run(
        [container_runtime, "volume", "create", name],
        capture_output=True,
        text=True,
        timeout=DAEMON_TIMEOUT_SECONDS,
        check=True,
    )
    try:
        yield name
    finally:
        subprocess.run(
            [container_runtime, "volume", "rm", "--force", name],
            capture_output=True,
            text=True,
            timeout=DAEMON_TIMEOUT_SECONDS,
            check=False,
        )


ImageRun = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def run_image(container_runtime: str, image: str) -> ImageRun:
    def perform(
        *,
        environment: dict[str, str] | None = None,
        mounts: dict[str, str] | None = None,
        arguments: Sequence[str] = (),
        entrypoint: str | None = None,
        network: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [container_runtime, "run", "--rm"]
        if network is not None:
            command += ["--network", network]
        for name, value in (environment or {}).items():
            command += ["--env", f"{name}={value}"]
        for source, destination in (mounts or {}).items():
            command += ["--volume", f"{source}:{destination}"]
        if entrypoint is not None:
            command += ["--entrypoint", entrypoint]
        command += [image, *arguments]
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            check=False,
        )

    return perform
