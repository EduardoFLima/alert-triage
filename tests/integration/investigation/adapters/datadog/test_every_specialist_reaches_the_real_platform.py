"""Confirms every declaration against the real platform and a real model.

Everything else about the investigation is exercised offline, against a fake
MCP server and a scripted model. Three things cannot be: that the tool names in
a declaration exist on Datadog's server, that the filter admits them, and that
a model given the instruction actually calls them. A fake proves none of those,
because a fake is built from the same assumptions the declaration is.

Parameterised over the crew rather than naming one specialist, so a specialist
added later cannot ship without its tool names confirmed against the real
server. It costs a model call and at least one platform call per specialist,
and per toolset a specialist declares, which is a developer's cost rather than
CI's: it needs real credentials and is skipped without them, so CI and a fresh
clone stay green.
"""

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import Investigation
from alert_triage.investigation.adapters.adk.agent import (
    Deployment,
    build_agent,
    build_manager,
    connection_for,
)
from alert_triage.investigation.adapters.adk.consultation import Consulted
from alert_triage.investigation.adapters.adk.credentials import (
    ALTERNATE_API_KEY_VARIABLE,
    API_KEY_VARIABLE,
    ENTERPRISE_VARIABLE,
    resolve_model_access,
)
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.adk.investigator import run_agent
from alert_triage.investigation.adapters.adk.model import build_model
from alert_triage.investigation.adapters.crew.roster import CREW
from alert_triage.investigation.adapters.crew.specialists.logs import (
    LOGS_SPECIALIST,
)
from alert_triage.investigation.adapters.datadog.links import ITEM_KEYS, DatadogLinks
from alert_triage.investigation.adapters.datadog.mcp import mcp_endpoint, mcp_headers
from alert_triage.investigation.contract import InvestigationTarget
from alert_triage.investigation.domain.specialist import Specialist, Toolset
from alert_triage.shared.window import Window
from alert_triage.triage.adapters.datadog.connection import (
    API_KEY_VARIABLE as DD_API_KEY_VARIABLE,
)
from alert_triage.triage.adapters.datadog.connection import (
    APP_KEY_VARIABLE,
    resolve_connection,
)


def _a_model_can_be_reached() -> bool:
    """Whether this environment can reach a model at all, by either route.

    Asked of the resolver rather than restated here. A deployment on the
    enterprise platform holds no key and is no less able to run these; naming
    ``GOOGLE_API_KEY`` in the gate would skip it for lacking something it is
    not supposed to have. Deferring keeps the gate agreeing with the thing it
    guards, including the alternate name the resolver already accepts.
    """
    try:
        resolve_model_access()
    except ConfigError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not (
        os.environ.get(DD_API_KEY_VARIABLE)
        and os.environ.get(APP_KEY_VARIABLE)
        and _a_model_can_be_reached()
    ),
    reason=(
        f"needs real {DD_API_KEY_VARIABLE} and {APP_KEY_VARIABLE}, and a way to "
        f"reach a model: {API_KEY_VARIABLE} or {ALTERNATE_API_KEY_VARIABLE}, or "
        f"{ENTERPRISE_VARIABLE} for the enterprise platform"
    ),
)

SERVICE = os.environ.get("ALERT_TRIAGE_LIVE_SERVICE", "checkout")
"""A service in the account under test. A quiet one is a valid answer."""

DECLARED_TOOLSETS = [
    (specialist.name, toolset) for specialist in CREW for toolset in specialist.toolsets
]
"""Every toolset the crew declares, named by the specialist that declared it.

Per toolset rather than per specialist: a specialist reaching two of them opens
a connection to each, and a failure has to say which half of it is missing.
"""


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


@pytest.mark.parametrize(
    ("specialist", "declared"),
    DECLARED_TOOLSETS,
    ids=[f"{name}-{toolset.name}" for name, toolset in DECLARED_TOOLSETS],
)
def test_every_declared_tool_exists_and_the_filter_admits_it(
    specialist: str, declared: Toolset
) -> None:
    """The one thing no fake can establish: that these names are real."""
    toolset = McpToolset(
        connection_params=connection_for(declared, _deployment()),
        tool_filter=list(declared.tools),
    )

    tools = asyncio.run(toolset.get_tools())

    assert {tool.name for tool in tools} == set(declared.tools)


@pytest.mark.parametrize(
    "specialist", CREW, ids=[specialist.name for specialist in CREW]
)
def test_a_real_model_given_the_instruction_calls_them(specialist: Specialist) -> None:
    """A quiet service is a valid answer; what must not happen is no retrieval."""
    retrieved = Retrieved()

    asyncio.run(
        run_agent(
            build_agent(specialist, _deployment(), retrieved), _target().describe()
        )
    )

    assert retrieved.retrievals >= 1
    assert retrieved.failures == ()


def _investigated() -> Retrieved:
    """One real consultation, kept with this account's addresses attached."""
    connection = resolve_connection()
    retrieved = Retrieved(link=DatadogLinks(connection.web_host))
    asyncio.run(
        run_agent(
            build_agent(LOGS_SPECIALIST, _deployment(), retrieved),
            _target().describe(),
        )
    )
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


def test_a_real_diagnostician_routes_over_the_real_crew(
    answers: Callable[[str], bool],
) -> None:
    """The one thing no fake settles: whether a manager actually chooses.

    A stub manager proves the routing is wired; it cannot prove a model given
    the instruction consults anybody, that a specialist's structured report
    survives the agent-tool hop, or that a confidence level comes back in the
    declared set. All three are what this establishes, and what tasks 8.3 to 8.6
    record the numbers from.
    """
    retrieved = Retrieved()
    consulted = Consulted(offered=CREW, retrieved=retrieved)

    concluded = asyncio.run(
        run_agent(
            build_manager(CREW, _deployment(), consulted, retrieved),
            _target().describe(),
        )
    )

    assert consulted.order, "the diagnostician consulted nobody at all"
    assert consulted.signals, "no signal was recorded as consulted"
    assert concluded.get("confidence") in {"high", "medium", "low"}
