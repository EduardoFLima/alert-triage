import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

DEFAULT_ENV_FILE = Path(".env")


def resolve_environment(
    path: Path = DEFAULT_ENV_FILE, env: Mapping[str, str] | None = None
) -> Mapping[str, str]:
    """Supplement the process environment without overriding it."""
    exported = os.environ if env is None else env
    return {**_declared(path), **exported}


def _declared(path: Path) -> Mapping[str, str]:
    """Drop bare names so they cannot shadow the process environment."""
    if not path.is_file():
        return {}
    return {
        name: value for name, value in dotenv_values(path).items() if value is not None
    }
