import subprocess
from collections.abc import Callable

PackagedRun = Callable[..., subprocess.CompletedProcess[str]]

MOUNTED_CONFIG = "/app/config.yaml"
RESOLVE_THE_CONFIG_PATH = (
    "from pathlib import Path; "
    "from alert_triage.configuration.adapters.yaml.loader import DEFAULT_CONFIG_PATH; "
    "print(Path(DEFAULT_CONFIG_PATH).resolve())"
)


def test_the_run_reads_its_config_from_the_path_the_mount_targets(
    run_image: PackagedRun,
) -> None:
    resolved = run_image(entrypoint="python", arguments=["-c", RESOLVE_THE_CONFIG_PATH])

    assert resolved.stdout.strip() == MOUNTED_CONFIG
