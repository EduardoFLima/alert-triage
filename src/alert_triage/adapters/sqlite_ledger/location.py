"""Where the ledger keeps its records.

Deliberately not part of the YAML-backed configuration, on the same rule that
put the Datadog site and credentials in the environment: ``config.yaml``
describes how the system behaves, and the same triage behavior runs from a
laptop, a container, and a scheduled job with three different paths. A key
naming a location written into the config file is inert.

Unlike a credential this has a default, because a path is not a secret and a
manual v1 run should need no configuration beyond ``scope.owner``. The default
is relative, so a run started from another directory starts from an empty
ledger — which is why a deployment is expected to set the variable explicitly.
"""

import os
from collections.abc import Mapping
from pathlib import Path

LEDGER_PATH_VARIABLE = "ALERT_TRIAGE_LEDGER_PATH"

DEFAULT_LEDGER_PATH = Path("alert_triage.db")


def resolve_ledger_path(env: Mapping[str, str] | None = None) -> Path:
    """Resolve where the ledger's SQLite database lives.

    Args:
        env: Environment to read from. Defaults to the process's.

    Returns:
        The path to the database file. It need not exist yet: the adapter
        creates its schema on first use.
    """
    environment = os.environ if env is None else env
    location = environment.get(LEDGER_PATH_VARIABLE)
    return Path(location) if location else DEFAULT_LEDGER_PATH
