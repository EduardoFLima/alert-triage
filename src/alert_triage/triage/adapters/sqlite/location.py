"""Where the ledger keeps its records.

Deliberately not part of the YAML-backed configuration, on the same rule that
put the Datadog site and credentials in the environment: ``config.yaml``
describes how the system behaves, and the same triage behavior runs from a
laptop, a container, and a scheduled job with three different paths. A key
naming a location written into the config file is inert.

Unlike a credential this has a default, because a path is not a secret and a
manual v1 run should need no configuration beyond ``scope.owner``. The default
is relative and sits under ``data/``, so a run from a checkout gathers its
state in one directory the repository ignores rather than beside the source.
Being relative, a run started from another directory starts from an empty
ledger — which is why a deployment is expected to set the variable explicitly.
"""

import os
from collections.abc import Mapping
from pathlib import Path

LEDGER_PATH_VARIABLE = "ALERT_TRIAGE_LEDGER_PATH"

DEFAULT_LEDGER_PATH = Path("data/alert_triage.db")


def resolve_ledger_path(env: Mapping[str, str] | None = None) -> Path:
    """Resolve where the ledger's SQLite database lives.

    Args:
        env: Environment to read from. Defaults to the process's.

    Returns:
        The path to the database file, ready to be opened: the directory
        holding it exists. The file itself need not — the adapter creates it
        with its schema on first use.
    """
    environment = os.environ if env is None else env
    location = environment.get(LEDGER_PATH_VARIABLE)
    return _ensure_ledger_directory(Path(location) if location else DEFAULT_LEDGER_PATH)


def _ensure_ledger_directory(path: Path) -> Path:
    """Make the directory the ledger's database sits in, if it is missing.

    SQLite creates the database file on first use but never the directory
    holding it, and both the default and a deployment's own path can name one
    that does not exist yet. Resolving a location means handing back one that
    can be opened, so this is part of resolving rather than a step a caller is
    expected to remember.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
