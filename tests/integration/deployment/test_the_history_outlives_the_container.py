"""The one thing containerizing breaks that a build alone never reveals.

A container's filesystem does not survive it. The ledger's default location is
relative to the working directory, so a packaged run left on that default keeps
its incident history *inside* the container — and every run then opens every
incident afresh, silently disabling dedup, continuation and the re-notify
cooldown while still exiting successfully.

These assert the ledger lands somewhere that outlives the run, and that a
second run finds what the first one left rather than writing over it.
"""

import subprocess
from collections.abc import Callable

from alert_triage.triage.adapters.sqlite import DEFAULT_LEDGER_PATH

PackagedRun = Callable[..., subprocess.CompletedProcess[str]]

LEDGER_DIRECTORY = "/var/lib/alert-triage"


def _contents_of(run_image: PackagedRun, volume: str) -> str:
    """Read the mount back with a throwaway container, after the run is gone."""
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
"""Seeded through the project's own adapter, so this asserts continuity rather
than reimplementing a schema it would then be free to get wrong."""

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


def test_a_configured_run_leaves_its_ledger_on_the_mount(
    run_image: PackagedRun,
    configured_environment: dict[str, str],
    ledger_volume: str,
) -> None:
    """What a run leaves on the mount, after the container holding it is gone.

    The run cannot reach its platform, but the ledger is opened before the
    fetch — so there is always something to have left behind.
    """
    run_image(
        environment=configured_environment,
        mounts={ledger_volume: LEDGER_DIRECTORY},
        network="none",
    )

    assert _contents_of(run_image, ledger_volume).strip() != ""


def test_the_ledger_takes_the_name_a_run_from_a_checkout_would_give_it(
    run_image: PackagedRun,
    configured_environment: dict[str, str],
    ledger_volume: str,
) -> None:
    """Only the directory differs from the default, never the filename.

    The README tells an operator to mount a checkout's own ``data/`` here to
    carry on from the history a local run built. That only works while both
    resolve to one file: a container writing some other name would sit beside
    the checkout's ledger reporting everything afresh, with two plausible
    databases in one directory and nothing saying which is live.

    Taken from the source rather than written out, so the two cannot drift.
    """
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
    """An incident recorded by one container, read back by the next.

    Without this, every run opens every incident afresh and the re-notify
    cooldown never suppresses anything.
    """
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
