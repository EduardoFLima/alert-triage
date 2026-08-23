"""Shared pytest configuration and fixtures for the whole suite."""

from pathlib import Path

import pytest

_SCOPE_MARKERS = frozenset({"unit", "integration"})


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
