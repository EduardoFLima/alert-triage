"""Reading a ``.env`` file into the environment a run resolves itself from.

The file is a convenience for a checkout, not a second source of truth: what
the process already exported wins over every name the file sets, so a
container or a scheduler is never overridden by a file that happened to be
lying beside the run. Every name is one an operator could equally have
exported by hand — this adds no setting of its own.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

DEFAULT_ENV_FILE = Path(".env")


def resolve_environment(
    path: Path = DEFAULT_ENV_FILE, env: Mapping[str, str] | None = None
) -> Mapping[str, str]:
    """Read the environment a run is configured from, ``.env`` file included.

    Args:
        path: Where the optional ``.env`` file would be. Its absence is fine:
            a deployment that exports everything needs no file.
        env: The process environment to supplement. Defaults to the process's.

    Returns:
        Every name the file and the process supply, the process's winning.
    """
    exported = os.environ if env is None else env
    return {**_declared(path), **exported}


def _declared(path: Path) -> Mapping[str, str]:
    """Read the names the file sets, dropping any it merely mentions.

    A bare ``NAME`` line declares nothing. Kept out entirely rather than
    carried as an empty string, so it cannot shadow a name the process
    exported.
    """
    if not path.is_file():
        return {}
    return {
        name: value for name, value in dotenv_values(path).items() if value is not None
    }
