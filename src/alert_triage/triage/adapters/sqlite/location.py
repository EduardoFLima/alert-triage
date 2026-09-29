import os
from collections.abc import Mapping
from pathlib import Path

LEDGER_PATH_VARIABLE = "ALERT_TRIAGE_LEDGER_PATH"

DEFAULT_LEDGER_PATH = Path("data/alert_triage.db")


def resolve_ledger_path(env: Mapping[str, str] | None = None) -> Path:
    environment = os.environ if env is None else env
    location = environment.get(LEDGER_PATH_VARIABLE)
    return _ensure_ledger_directory(Path(location) if location else DEFAULT_LEDGER_PATH)


def _ensure_ledger_directory(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
