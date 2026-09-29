import subprocess
from collections.abc import Callable

from alert_triage.triage.adapters.sqlite import DEFAULT_LEDGER_PATH

PackagedRun = Callable[..., subprocess.CompletedProcess[str]]

LEDGER_DIRECTORY = "/var/lib/alert-triage"


def _contents_of(run_image: PackagedRun, volume: str) -> str:
    return run_image(
        mounts={volume: LEDGER_DIRECTORY},
        entrypoint="/bin/sh",
        arguments=["-c", f"ls {LEDGER_DIRECTORY}"],
    ).stdout


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
            id="survives-the-container",
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


def test_the_ledger_takes_the_name_a_run_from_a_checkout_would_give_it(
    run_image: PackagedRun,
    configured_environment: dict[str, str],
    ledger_volume: str,
) -> None:
    run_image(
        environment=configured_environment,
        mounts={ledger_volume: LEDGER_DIRECTORY},
        network="none",
    )

    left_behind = _contents_of(run_image, ledger_volume).split()

    assert DEFAULT_LEDGER_PATH.name in left_behind


def test_a_second_container_keeps_what_the_first_one_left(
    run_image: PackagedRun, ledger_volume: str
) -> None:
    recorded = run_image(
        mounts={ledger_volume: LEDGER_DIRECTORY},
        entrypoint="python",
        arguments=["-c", RECORD_AN_INCIDENT],
    )
    assert recorded.returncode == 0, recorded.stderr

    read_back = run_image(
        mounts={ledger_volume: LEDGER_DIRECTORY},
        entrypoint="python",
        arguments=["-c", READ_IT_BACK],
    )

    assert "survives-the-container" in read_back.stdout
