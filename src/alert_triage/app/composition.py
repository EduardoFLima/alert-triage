"""The one place concrete adapters are named, built, and handed to the run.

Everything the pipeline depends on is resolved here and injected there, which
is what keeps ``run`` free of any integration and what makes swapping one — a
second platform, another channel, a different store — a change to this module
alone.

Configuration is resolved before anything is built: a deployment missing its
scope or its only notification channel refuses to start, rather than fetching
alerts it could tell nobody about.
"""

import sqlite3
import uuid
from collections.abc import Mapping
from contextlib import closing
from datetime import datetime
from pathlib import Path

from alert_triage.adapters.datadog.alert_source import build_alert_source
from alert_triage.adapters.datadog.connection import resolve_connection
from alert_triage.adapters.fan_out.resolution import resolve_notifier
from alert_triage.adapters.sqlite_ledger.ledger import SqliteTriageLedger
from alert_triage.adapters.sqlite_ledger.location import resolve_ledger_path
from alert_triage.adapters.yaml_config.loader import DEFAULT_CONFIG_PATH, load_config
from alert_triage.app.run import RunOutcome, run
from alert_triage.domain.report import build_pass_through_report


def execute(
    *,
    now: datetime,
    env: Mapping[str, str] | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> RunOutcome:
    """Build everything one run needs, run it, and let go of what it opened.

    Args:
        now: The instant the run decides against, taken once by the caller.
        env: Environment the deployment facts are read from. Defaults to the
            process's.
        config_path: Where the optional config file would be.

    Returns:
        What the run handled, delivered, and could not do.

    Raises:
        ConfigError: The deployment is not configured well enough to run —
            the scope is missing, a credential is absent, or no channel is
            configured. Nothing is fetched and nothing is delivered.
    """
    config = load_config(config_path, env)
    connection = resolve_connection(env)
    notifier = resolve_notifier(env)
    source = build_alert_source(connection, config.ingestion, config.scope.owner)

    with closing(sqlite3.connect(resolve_ledger_path(env))) as database:
        return run(
            source=source,
            ledger=SqliteTriageLedger(
                database,
                window=config.grouping.window,
                cooldown=config.re_notify.cooldown,
                retention=config.ledger.retention,
            ),
            notifier=notifier,
            build_report=build_pass_through_report,
            config=config,
            now=now,
            new_id=_new_id,
        )


def _new_id() -> str:
    """Name a newly opened incident.

    A random UUID rather than anything derived from the alerts: an incident
    keeps its name while it absorbs more of them, and two runs must never
    arrive at the same name for two different problems.
    """
    return str(uuid.uuid4())
