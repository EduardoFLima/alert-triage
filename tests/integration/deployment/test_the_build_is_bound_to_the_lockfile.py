import shutil
import subprocess
from pathlib import Path

BUILD_TIMEOUT_SECONDS = 900.0

CONTEXT = ("Dockerfile", "pyproject.toml", "uv.lock", "README.md", "LICENSE")


def test_a_lockfile_that_disagrees_with_the_project_fails_the_build(
    container_runtime: str, repository_root: Path, tmp_path: Path
) -> None:
    for name in CONTEXT:
        shutil.copy(repository_root / name, tmp_path / name)
    shutil.copytree(repository_root / "src", tmp_path / "src")

    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        manifest.read_text().replace(
            '    "pyyaml>=6.0",',
            '    "pyyaml>=6.0",\n    "a-dependency-the-lockfile-never-saw",',
        )
    )

    built = subprocess.run(
        [container_runtime, "build", "--tag", "alert-triage:stale", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=BUILD_TIMEOUT_SECONDS,
        check=False,
    )

    assert built.returncode != 0
    assert "lockfile" in (built.stdout + built.stderr).lower()
