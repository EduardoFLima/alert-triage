"""The compose file exists to be the repeat run, so it is tested as one.

``docker run`` without ``-v`` keeps no history and says nothing about it. The
compose file is the answer to that — the mount written down once, so a second
run reaches the first run's ledger without anyone re-typing it. A compose file
that did not actually achieve this would be worse than none, because the README
would be sending people to it.
"""

import subprocess
from pathlib import Path
from uuid import uuid4

COMPOSE_TIMEOUT_SECONDS = 900.0

RECORD_AN_INCIDENT = """
import os, sqlite3
from datetime import UTC, datetime, timedelta
from alert_triage.triage.adapters.sqlite.ledger import SqliteTriageLedger
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.incident import Incident

now = datetime.now(UTC)
with sqlite3.connect(os.environ["ALERT_TRIAGE_LEDGER_PATH"]) as database:
    SqliteTriageLedger(
        database,
        window=timedelta(minutes=30),
        cooldown=timedelta(days=2),
        retention=timedelta(days=30),
    ).record(
        Incident(
            id="survives-between-compose-runs",
            service="checkout",
            alerts=(Alert(service="checkout", fired_at=now),),
        ),
        now,
    )
"""

READ_IT_BACK = """
import os, sqlite3
from datetime import UTC, datetime, timedelta
from alert_triage.triage.adapters.sqlite.ledger import SqliteTriageLedger

with sqlite3.connect(os.environ["ALERT_TRIAGE_LEDGER_PATH"]) as database:
    ledger = SqliteTriageLedger(
        database,
        window=timedelta(minutes=30),
        cooldown=timedelta(days=2),
        retention=timedelta(days=30),
    )
    for incident in ledger.open_incidents("checkout", datetime.now(UTC)):
        print(incident.id)
"""


def test_two_compose_runs_share_one_ledger(
    compose_command: list[str], repository_root: Path
) -> None:
    """Two runs, one ledger, through the invocation the README documents.

    The project name is its own, so this never touches an operator's real
    volume and takes its own with it on the way out.
    """
    project = f"alert-triage-test-{uuid4().hex[:12]}"
    base = [*compose_command, "--project-name", project]

    def run(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*base, "run", "--rm", "--entrypoint", "python", "triage", "-c", script],
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=COMPOSE_TIMEOUT_SECONDS,
            check=False,
        )

    try:
        recorded = run(RECORD_AN_INCIDENT)
        assert recorded.returncode == 0, recorded.stderr

        read_back = run(READ_IT_BACK)

        assert "survives-between-compose-runs" in read_back.stdout
    finally:
        subprocess.run(
            [*base, "down", "--volumes"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=COMPOSE_TIMEOUT_SECONDS,
            check=False,
        )
