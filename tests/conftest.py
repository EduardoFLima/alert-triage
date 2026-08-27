"""Shared pytest configuration and fixtures for the whole suite."""

import os
from pathlib import Path

import pytest

_SCOPE_MARKERS = frozenset({"unit", "integration"})


@pytest.fixture
def process_environment(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """The process environment, emptied, for a test that reads it by default.

    A few tests establish that a caller passing no environment is handed the
    process's. They are the only ones reading it for real, which makes them the
    only ones a developer's own exports can answer for — and sourcing a ``.env``
    to run the live checks is exactly how those exports arrive.

    Emptying it beats deleting the names one at a time. That list is stale the
    moment a setting is added, it goes stale silently, and it fails in whichever
    direction the shell happens to lean: a name the file exports must be deleted
    here, and deleting a name CI never sets raises instead.

    Returns:
        The environment those tests read, to be filled with exactly what the
        behaviour under test needs and nothing else.
    """
    environment: dict[str, str] = {}
    monkeypatch.setattr(os, "environ", environment)
    return environment


@pytest.fixture(scope="session")
def repository_root() -> Path:
    """The checkout a test reads a shipped file out of.

    Found by its marker rather than by counting parent directories, so moving
    a test deeper into the mirrored tree does not silently point it at the
    wrong place.
    """
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise AssertionError("No repository root above the test suite")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark each test by the directory it lives in.

    Scope is decided by placement rather than by hand-written markers: a
    developer can forget the decorator, but not the directory.
    """
    tests_root = Path(__file__).parent
    for item in items:
        relative = item.path.relative_to(tests_root)
        scope = relative.parts[0]
        if scope in _SCOPE_MARKERS:
            item.add_marker(scope)
