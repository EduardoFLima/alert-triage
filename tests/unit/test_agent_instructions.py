from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "AGENTS.md"
HARNESS_FILENAMES = ("CLAUDE.md", "GEMINI.md")


@pytest.mark.parametrize("filename", HARNESS_FILENAMES)
def test_harness_file_is_a_symlink_to_the_canonical_file(filename: str) -> None:
    path = REPO_ROOT / filename

    assert CANONICAL.is_file()
    assert path.is_symlink(), (
        f"{filename} must be a symlink to AGENTS.md, not an independent copy"
    )
    assert path.resolve() == CANONICAL.resolve()
    assert path.read_bytes() == CANONICAL.read_bytes()
