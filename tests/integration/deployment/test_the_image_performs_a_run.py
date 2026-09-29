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


def test_a_packaged_run_refuses_on_the_setting_that_has_no_default(
    run_image: PackagedRun,
) -> None:
    result = run_image()

    assert result.returncode != 0
    assert "scope.owner" in result.stderr


def test_a_configured_run_gets_all_the_way_to_the_platform(
    run_image: PackagedRun,
    configured_environment: dict[str, str],
    ledger_volume: str,
) -> None:
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
    declared = subprocess.run(
        [container_runtime, "inspect", "--format", "{{json .Config.Cmd}}", image],
        capture_output=True,
        text=True,
        timeout=30.0,
        check=True,
    )

    assert declared.stdout.strip() in {"null", "[]"}
