import os
import sqlite3
import uuid
from collections.abc import Mapping
from contextlib import closing
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from alert_triage.app.pipeline import RunOutcome, run
from alert_triage.configuration.adapters.yaml.loader import (
    DEFAULT_CONFIG_PATH,
    load_config,
)
from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import CircuitBreakers, Investigation
from alert_triage.investigation.adapters.adk.agent import Deployment, PlatformAccess
from alert_triage.investigation.adapters.adk.credentials import resolve_model_access
from alert_triage.investigation.adapters.adk.guides import fetch_guides
from alert_triage.investigation.adapters.adk.investigator import (
    AdkInvestigator,
    report_with_adk,
    run_with_adk,
)
from alert_triage.investigation.adapters.adk.model import build_model
from alert_triage.investigation.adapters.crew.roster import crew_for
from alert_triage.investigation.adapters.datadog.links import DatadogLinks
from alert_triage.investigation.adapters.datadog.mcp import (
    DATADOG,
    mcp_endpoint,
    mcp_headers,
)
from alert_triage.investigation.ports.investigator import Investigator
from alert_triage.notification.adapters.email.notifier import EmailNotifier
from alert_triage.notification.adapters.email.settings import resolve_email_settings
from alert_triage.notification.adapters.fan_out import FanOutNotifier
from alert_triage.notification.adapters.teams.notifier import TeamsNotifier
from alert_triage.notification.adapters.teams.settings import resolve_teams_webhook_url
from alert_triage.notification.ports.notifier import Notifier
from alert_triage.triage.adapters.datadog.alert_source import build_alert_source
from alert_triage.triage.adapters.datadog.connection import (
    DatadogConnection,
    resolve_connection,
)
from alert_triage.triage.adapters.sqlite.ledger import SqliteTriageLedger
from alert_triage.triage.adapters.sqlite.location import resolve_ledger_path
from alert_triage.triage.domain.report import build_report

if TYPE_CHECKING:
    from google.adk.models import BaseLlm


def execute(
    *,
    now: datetime,
    env: Mapping[str, str] | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> RunOutcome:
    """Assemble everything before fetching, so setup failures spend no work."""
    config = load_config(config_path, env)
    datadog_connection = resolve_connection(env)
    notifier = resolve_notifier(env)
    source = build_alert_source(
        datadog_connection,
        config.ingestion,
        config.scope.owner,
        tuple(config.scope.services),
        env=config.scope.env,
    )
    investigator = build_investigator(
        env, datadog_connection, config.investigation, config.circuit_breakers
    )

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


def resolve_notifier(env: Mapping[str, str] | None = None) -> FanOutNotifier:
    """Refuse deployments that can investigate but tell nobody what they found."""
    environment = os.environ if env is None else env
    channels = _configured_channels(environment)
    if not channels:
        raise ConfigError(
            "No notification channel is configured: set at least one "
            "notification channel in the environment. A run that can tell "
            "nobody what it found has no reason to start."
        )
    return FanOutNotifier(channels)


def _configured_channels(env: Mapping[str, str]) -> list[Notifier]:
    channels: list[Notifier] = []
    email = resolve_email_settings(env)
    if email is not None:
        channels.append(EmailNotifier(email))
    webhook_url = resolve_teams_webhook_url(env)
    if webhook_url is not None:
        channels.append(TeamsNotifier(webhook_url))
    return channels


def build_investigator(
    env: Mapping[str, str] | None,
    datadog_connection: DatadogConnection,
    investigation: Investigation,
    breakers: CircuitBreakers | None = None,
) -> Investigator:
    """Build guides and model access before any alert is fetched."""
    access = resolve_model_access(env)
    default = build_model(investigation.model, access)

    def _model_for(named: str | None) -> "str | BaseLlm":
        return default if named is None else build_model(named, access)

    deployment = Deployment(
        platforms={
            DATADOG: PlatformAccess(
                endpoint=mcp_endpoint(datadog_connection.site),
                headers=mcp_headers(
                    api_key=datadog_connection.api_key,
                    app_key=datadog_connection.app_key,
                ),
            )
        },
        model_for=_model_for,
        breakers=breakers or CircuitBreakers(),
    )
    crew = crew_for(investigation.specialists, providers=set(deployment.platforms))
    deployment = replace(deployment, guides=fetch_guides(crew, deployment))
    return AdkInvestigator(
        crew=crew,
        links=DatadogLinks(datadog_connection.web_host),
        run_diagnostician=run_with_adk(deployment),
        run_report=report_with_adk(deployment),
        breakers=deployment.breakers,
    )


def _new_id() -> str:
    """Use a random name because incidents grow as new alerts join them."""
    return str(uuid.uuid4())
