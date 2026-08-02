"""Shared pytest configuration and fixtures for the whole suite."""

from pathlib import Path

import pytest

_SCOPE_MARKERS = frozenset({"unit", "integration"})


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
