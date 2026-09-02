"""Fixtures for the tests that exercise the distributable image.

These are the only tests that need something outside the interpreter that is
not a credential: a container runtime. They follow the same discipline the
credential-gated tests follow — skip, saying why, when the prerequisite is
absent — so a checkout without Docker still runs green and a developer running
``pytest -rs`` is told what did not run.

The image itself is resolved rather than assumed. A gate that has already built
one names it in the environment and these tests use it as-is; a developer who
has not gets one built from the checkout they are sitting in.
"""

import os
import shutil
import subprocess
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from uuid import uuid4

import pytest

IMAGE_VARIABLE = "ALERT_TRIAGE_IMAGE"
"""Names an already-built image, so a gate builds once and the tests reuse it."""

DEFAULT_IMAGE = "alert-triage:test"
"""What a developer with no gate gets, built from their own checkout."""

LEDGER_DIRECTORY = "/var/lib/alert-triage"
"""Where the image keeps the ledger, and so what a durable mount is mounted at."""

DAEMON_TIMEOUT_SECONDS = 30.0
"""How long the runtime is given to admit it is there."""

BUILD_TIMEOUT_SECONDS = 900.0
"""A cold build resolves and installs the whole dependency set."""

RUN_TIMEOUT_SECONDS = 180.0
"""Long enough for a run that reaches the platform, short enough to fail a hang."""


@pytest.fixture(scope="session")
def container_runtime() -> str:
    """The runtime command, or a skip naming which half of the check failed.

    Two things can be missing and they are worth telling apart: a machine with
    no Docker installed at all, and one where it is installed but the daemon is
    not running. The second is the common developer case, and a bare "docker not
    available" would send them looking for an install they already have.
    """
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
    """The image under test, built from the checkout unless one was supplied.

    A supplied tag is trusted and never rebuilt: that is the gate's contract,
    where the build is its own step so a broken Dockerfile fails as a build
    rather than as a confusing test error. Where nothing supplied one, a failed
    build fails the tests loudly rather than skipping them — skipping is for a
    missing prerequisite, and a Dockerfile that will not build is a defect.
    """
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
    """Everything a run refuses to start without, and a platform it cannot reach.

    The point is to get past configuration and no further: a run that resolves
    all of this has built every adapter it needs, which is the whole of what the
    image is answerable for.

    The site is a real one and the credentials are not, because the platform is
    put out of reach by running the container on no network rather than by
    naming somewhere that does not exist. ``DD_SITE`` is checked against the
    vendor client's own allowlist, so an invented site fails that check instead
    of failing to connect — a different failure, reached before any adapter has
    to work. No test here touches a real account.
    """
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
    """Compose, however this machine has it, or a skip saying it has neither.

    It ships two ways — as a ``docker`` subcommand and as a standalone binary —
    and a machine may have either. Preferring the subcommand and falling back
    keeps the test honest about what it is exercising without making the
    documented invocation depend on which one an operator installed.
    """
    subcommand = [container_runtime, "compose"]
    if _answers(subcommand):
        return subcommand
    standalone = shutil.which("docker-compose")
    if standalone is not None and _answers([standalone]):
        return [standalone]
    pytest.skip("no compose: neither `docker compose` nor `docker-compose` answered")


def _answers(command: list[str]) -> bool:
    """Whether this form of compose is installed and willing to say its version."""
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
    """A named volume for the run's history, torn down with the test.

    Named rather than a bind mount because a named volume is initialised with
    the image's own ownership. A host directory would arrive owned by whoever
    runs the suite — which on a developer's machine is invisible and in CI is a
    failure — and that is a property of the host, not of the image.
    """
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
    """Perform one packaged run, the way anything starting the image would.

    A container begins with only the environment the image sets, so unlike the
    installed-distribution tests there is nothing here to empty first: what the
    run resolves is exactly what a caller passed it.
    """

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
