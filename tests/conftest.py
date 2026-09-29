import os
from pathlib import Path

import pytest

_SCOPE_MARKERS = frozenset({"unit", "integration"})


@pytest.fixture
def process_environment(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Patch ``os.environ`` itself so default-read tests cannot see the shell."""
    environment: dict[str, str] = {}
    monkeypatch.setattr(os, "environ", environment)
    return environment


@pytest.fixture(scope="session")
def repository_root() -> Path:
    """Find the checkout by marker so deeper tests do not change the answer."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise AssertionError("No repository root above the test suite")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Scope markers come from placement, not hand-written decorators."""
    tests_root = Path(__file__).parent
    for item in items:
        relative = item.path.relative_to(tests_root)
        scope = relative.parts[0]
        if scope in _SCOPE_MARKERS:
            item.add_marker(scope)
