from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def config_example(repository_root: Path) -> Path:
    return repository_root / "config.example.yaml"


@pytest.fixture(scope="session")
def env_example(repository_root: Path) -> Path:
    return repository_root / ".env.example"
