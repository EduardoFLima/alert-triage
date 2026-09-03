"""The image runs the versions the gate verified, or it does not build.

``uv sync --frozen`` is what makes that true: the lockfile is authoritative and
a lockfile that disagrees with ``pyproject.toml`` is an error rather than an
invitation to resolve something else. Without it an image could quietly ship a
dependency set no test ever ran against, which is the whole value of shipping a
lockfile in the first place.
"""

import shutil
import subprocess
from pathlib import Path

BUILD_TIMEOUT_SECONDS = 900.0

CONTEXT = ("Dockerfile", "pyproject.toml", "uv.lock", "README.md", "LICENSE")
"""Everything the build reads, which is what a stand-in context has to hold."""


def test_a_lockfile_that_disagrees_with_the_project_fails_the_build(
    container_runtime: str, repository_root: Path, tmp_path: Path
) -> None:
    """A dependency the lockfile has never seen is the cheapest disagreement."""
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
