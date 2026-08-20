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

from alert_triage.adapters.adk.investigator import AdkInvestigator, run_with_adk
from alert_triage.adapters.datadog.alert_source import build_alert_source
from alert_triage.adapters.datadog.connection import (
    DatadogConnection,
    resolve_connection,
)
from alert_triage.adapters.datadog.mcp_platform import DatadogMcpPlatform
from alert_triage.adapters.fan_out.resolution import resolve_notifier
from alert_triage.adapters.sqlite_ledger.ledger import SqliteTriageLedger
from alert_triage.adapters.sqlite_ledger.location import resolve_ledger_path
from alert_triage.adapters.yaml_config.loader import DEFAULT_CONFIG_PATH, load_config
from alert_triage.app.run import RunOutcome, run
from alert_triage.domain.report import build_report
from alert_triage.ports.config import Investigation
from alert_triage.ports.investigator import Investigator


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
    datadog = resolve_connection(env)
    notifier = resolve_notifier(env)
    source = build_alert_source(datadog, config.ingestion, config.scope.owner)
    investigator = build_investigator(datadog, config.investigation)

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
            investigator=investigator,
            build_report=build_report,
            config=config,
            now=now,
            new_id=_new_id,
        )


def build_investigator(
    datadog: DatadogConnection, investigation: Investigation
) -> Investigator:
    """Assemble the agent crew over the platform it gathers evidence from.

    A named function rather than an inline construction so that a test can
    substitute the one adapter that would otherwise reach both a model and an
    MCP server, exactly as it already substitutes the alert source and the
    notifier.

    Args:
        datadog: Where Datadog is and how to authenticate.
        investigation: How an investigation reasons.

    Returns:
        The investigator a run is handed.
    """
    return AdkInvestigator(
        platform=DatadogMcpPlatform(datadog),
        run_agent=run_with_adk(investigation.model),
    )


def _new_id() -> str:
    """Name a newly opened incident.

    A random UUID rather than anything derived from the alerts: an incident
    keeps its name while it absorbs more of them, and two runs must never
    arrive at the same name for two different problems.
    """
    return str(uuid.uuid4())
