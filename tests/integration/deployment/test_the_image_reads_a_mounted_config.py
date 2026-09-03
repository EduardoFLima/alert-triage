"""Where a packaged run looks for its behaviour, which a mount has to agree with.

``config.yaml`` is resolved relative to the working directory, and the image's
working directory is ``/app``. ``/app/config.yaml`` is therefore the target the
README's ``docker run`` and its ``compose.override.yaml`` both name, and the
only reason either works. Nothing states that correspondence: it is a default
in one module and a ``WORKDIR`` in the Dockerfile, and moving either would
break both instructions while every other test stayed green.

Asked of the image rather than of a mount, because a mount cannot answer it
here. Docker Desktop does not share ``/private/var/folders``, where pytest puts
``tmp_path``, so a bind mount from there is silently replaced by an empty
directory — the config would read as absent for a reason that has nothing to do
with whether the path is right.
"""

import subprocess
from collections.abc import Callable

PackagedRun = Callable[..., subprocess.CompletedProcess[str]]

MOUNTED_CONFIG = "/app/config.yaml"
"""What the README tells an operator to mount their config file at."""

RESOLVE_THE_CONFIG_PATH = (
    "from pathlib import Path; "
    "from alert_triage.configuration.adapters.yaml.loader import DEFAULT_CONFIG_PATH; "
    "print(Path(DEFAULT_CONFIG_PATH).resolve())"
)
"""Resolved inside the container, so the working directory answering is the
image's own and the default answering is the installed package's own."""


def test_the_run_reads_its_config_from_the_path_the_mount_targets(
    run_image: PackagedRun,
) -> None:
    """The documented mount target is where a packaged run actually looks."""
    resolved = run_image(entrypoint="python", arguments=["-c", RESOLVE_THE_CONFIG_PATH])

    assert resolved.stdout.strip() == MOUNTED_CONFIG
