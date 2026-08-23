"""The shipped example files these tests read, located once."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def config_example(repository_root: Path) -> Path:
    """The config file an operator copies to ``config.yaml``."""
    return repository_root / "config.example.yaml"


@pytest.fixture(scope="session")
def env_example(repository_root: Path) -> Path:
    """The environment file an operator copies to ``.env``."""
    return repository_root / ".env.example"
