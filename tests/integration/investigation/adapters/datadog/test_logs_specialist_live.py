"""Confirms the declaration against the real platform and a real model.

Everything else about the investigation is exercised offline, against a fake
MCP server and a scripted model. Three things cannot be: that the tool names in
the declaration exist on Datadog's server, that the filter admits them, and
that a model given the instruction actually calls them. A fake proves none of
those, because a fake is built from the same assumptions the declaration is.

It needs real credentials and is skipped without them, so CI and a fresh clone
stay green. It costs a model call and a platform call when it does run.
"""

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from alert_triage.configuration.settings import Investigation
from alert_triage.investigation.adapters.adk.agent import Deployment, connection_for
from alert_triage.investigation.adapters.adk.credentials import (
    API_KEY_VARIABLE,
    resolve_model_access,
)
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.adk.investigator import run_with_adk
from alert_triage.investigation.adapters.adk.model import build_model
from alert_triage.investigation.adapters.datadog.links import ITEM_KEYS, DatadogLinks
from alert_triage.investigation.adapters.datadog.mcp import mcp_endpoint, mcp_headers
from alert_triage.investigation.adapters.datadog.specialists.logs import LOGS_SPECIALIST
from alert_triage.investigation.contract import InvestigationTarget
from alert_triage.shared.window import Window
from alert_triage.triage.adapters.datadog.connection import (
    API_KEY_VARIABLE as DD_API_KEY_VARIABLE,
)
from alert_triage.triage.adapters.datadog.connection import (
    APP_KEY_VARIABLE,
    resolve_connection,
)

pytestmark = pytest.mark.skipif(
    not (
        os.environ.get(DD_API_KEY_VARIABLE)
        and os.environ.get(APP_KEY_VARIABLE)
        and os.environ.get(API_KEY_VARIABLE)
    ),
    reason=(
        f"needs real {DD_API_KEY_VARIABLE}, {APP_KEY_VARIABLE} and {API_KEY_VARIABLE}"
    ),
)

SERVICE = os.environ.get("ALERT_TRIAGE_LIVE_SERVICE", "checkout")
"""A service in the account under test. A quiet one is a valid answer."""


def _deployment() -> Deployment:
    connection = resolve_connection()
    model = build_model(Investigation.DEFAULT_MODEL, resolve_model_access())
    return Deployment(
        endpoint=mcp_endpoint(connection.site),
        headers=mcp_headers(api_key=connection.api_key, app_key=connection.app_key),
        model_for=lambda named: model,
    )


def _target() -> InvestigationTarget:
    fired_at = datetime.now(UTC) - timedelta(minutes=30)
    return InvestigationTarget(
        service=SERVICE,
        window=Window(start=fired_at, end=fired_at),
        alert_count=1,
    )


def test_the_declared_log_tools_exist_and_the_filter_admits_them() -> None:
    """The one thing no fake can establish: that these names are real."""
    (declared,) = LOGS_SPECIALIST.toolsets
    toolset = McpToolset(
        connection_params=connection_for(declared, _deployment()),
        tool_filter=list(declared.tools),
    )

    tools = asyncio.run(toolset.get_tools())

    assert {tool.name for tool in tools} == set(declared.tools)


def test_a_real_model_given_the_instruction_calls_them() -> None:
    """A quiet service is a valid answer; what must not happen is no retrieval."""
    retrieved = Retrieved()

    run_with_adk(_deployment())(LOGS_SPECIALIST, retrieved, _target().describe())

    assert retrieved.retrievals >= 1
    assert retrieved.failures == ()


def _investigated() -> Retrieved:
    """One real investigation, kept with this account's addresses attached."""
    connection = resolve_connection()
    retrieved = Retrieved(link=DatadogLinks(connection.site))
    run_with_adk(_deployment())(LOGS_SPECIALIST, retrieved, _target().describe())
    return retrieved


def test_an_address_built_from_a_real_retrieval_opens_rather_than_404s(
    answers: Callable[[str], bool],
) -> None:
    """A unit test asserts the string; only Datadog says whether it is a route."""
    retrieved = _investigated()

    address = retrieved.resolve("call-1").url  # type: ignore[union-attr]

    assert address is not None
    assert answers(address), f"the platform serves nothing at {address}"


def test_what_key_a_live_log_payload_identifies_an_item_by() -> None:
    """The design's open question, answered by a real payload rather than a guess.

    Per-item addressing is the optimisation and the retrieval's own address is
    the fallback, so a payload naming an item under none of the keys this
    adapter reads is a finding to fold back into ``ITEM_KEYS`` — not a broken
    link. What this records is which of them a live payload actually uses.
    """
    retrieved = _investigated()

    item = retrieved.resolve("call-1/item-1")
    if item is None:
        pytest.skip(f"the logs of {SERVICE!r} were quiet, so no item was returned")

    payload = item.payload if isinstance(item.payload, dict) else {}
    named = [key for key in ITEM_KEYS if payload.get(key)]
    print(f"a live log item is identified by {named or f'none of {ITEM_KEYS}'}")
    print(f"the keys a live log item carries are {sorted(payload)}")
    assert item.url is not None
