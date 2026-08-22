"""The one place concrete adapters are named, built, and handed to the run.

Everything the pipeline depends on is resolved here and injected there, which
is what keeps ``run`` free of any integration and what makes swapping one — a
second platform, another channel, a different store — a change to this module
alone.

Nothing is fetched until everything is assembled, and each piece refuses over
what it alone needs: a deployment missing its scope, its only notification
channel, or the credential its investigations reason on stops here, rather
than fetching alerts it could tell nobody about or investigate.
"""

import sqlite3
import uuid
from collections.abc import Mapping
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from alert_triage.adapters.adk.credentials import resolve_model_access
from alert_triage.adapters.adk.crew import crew_for
from alert_triage.adapters.adk.investigator import AdkInvestigator, run_with_adk
from alert_triage.adapters.adk.model import build_model
from alert_triage.adapters.adk.specialists import Deployment
from alert_triage.adapters.datadog.alert_source import build_alert_source
from alert_triage.adapters.datadog.connection import (
    DatadogConnection,
    resolve_connection,
)
from alert_triage.adapters.datadog.datadog_mcp import mcp_endpoint, mcp_headers
from alert_triage.adapters.fan_out.resolution import resolve_notifier
from alert_triage.adapters.sqlite_ledger.ledger import SqliteTriageLedger
from alert_triage.adapters.sqlite_ledger.location import resolve_ledger_path
from alert_triage.adapters.yaml_config.loader import DEFAULT_CONFIG_PATH, load_config
from alert_triage.app.run import RunOutcome, run
from alert_triage.domain.report import build_report
from alert_triage.ports.config import Investigation
from alert_triage.ports.investigator import Investigator

if TYPE_CHECKING:
    from google.adk.models import BaseLlm


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
            the scope is missing, a platform or model credential is absent, or
            no channel is configured. Nothing is fetched and nothing is
            delivered.
    """
    config = load_config(config_path, env)
    datadog_connection = resolve_connection(env)
    notifier = resolve_notifier(env)
    source = build_alert_source(
        datadog_connection, config.ingestion, config.scope.owner
    )
    investigator = build_investigator(env, datadog_connection, config.investigation)

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
    env: Mapping[str, str] | None,
    datadog_connection: DatadogConnection,
    investigation: Investigation,
) -> Investigator:
    """Assemble the agent crew over the platform it gathers evidence from.

    A named function rather than an inline construction so that a test can
    substitute the one adapter that would otherwise reach both a model and an
    MCP server, exactly as it already substitutes the alert source and the
    notifier.

    What is supplied here is a deployment: where the platform is, what
    authenticates against it, and how a specialist reaches the model it
    reasons on. No tool is named — which tools a specialist may reach is its
    declaration's business, and adding one changes nothing here.

    The model's credential is checked here rather than beside the other
    startup checks because this is what needs it: a deployment that stops
    building an investigator stops needing a key, and a check kept somewhere
    that merely remembers to run it would outlive what it guards.

    Args:
        env: Environment the model's credential is read from, or ``None`` for
            the process's.
        datadog_connection: Where Datadog is and how to authenticate.
        investigation: How an investigation reasons.

    Returns:
        The investigator a run is handed.

    Raises:
        ConfigError: The model has no credential, or a specialist was
            configured that nobody declared. Refused while the run is still
            being assembled, so no alert is fetched and no attempt is spent
            discovering it — and refused on the same value the model is then
            built from, so the two cannot disagree.
    """
    access = resolve_model_access(env)
    default = build_model(investigation.model, access)

    def _model_for(named: str | None) -> "str | BaseLlm":
        """The model a specialist reasons on, built where it named its own."""
        return default if named is None else build_model(named, access)

    return AdkInvestigator(
        crew=crew_for(investigation.specialists),
        run_specialist=run_with_adk(
            Deployment(
                endpoint=mcp_endpoint(datadog_connection),
                headers=mcp_headers(datadog_connection),
                model_for=_model_for,
            )
        ),
    )


def _new_id() -> str:
    """Name a newly opened incident.

    A random UUID rather than anything derived from the alerts: an incident
    keeps its name while it absorbs more of them, and two runs must never
    arrive at the same name for two different problems.
    """
    return str(uuid.uuid4())
