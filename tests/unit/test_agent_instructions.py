from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "AGENTS.md"
HARNESS_FILENAMES = ("CLAUDE.md", "GEMINI.md")


def test_canonical_instruction_file_exists() -> None:
    assert CANONICAL.is_file()


@pytest.mark.parametrize("filename", HARNESS_FILENAMES)
def test_harness_file_is_a_symlink_to_the_canonical_file(filename: str) -> None:
    """A copy would drift; an editor or a Windows checkout can silently make one."""
    path = REPO_ROOT / filename

    assert path.is_symlink(), (
        f"{filename} must be a symlink to AGENTS.md, not an independent copy"
    )
    assert path.resolve() == CANONICAL.resolve()
    assert path.read_bytes() == CANONICAL.read_bytes()
