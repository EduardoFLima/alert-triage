"""Exercise every crew declaration against real Datadog and a real model.

Live calls confirm tool names, guide coverage, and model-initiated calls that
fakes cannot prove; the suite skips without credentials.
"""

import asyncio
import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

import pytest
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from alert_triage.configuration.adapters.yaml.loader import (
    DEFAULT_CONFIG_PATH,
    load_config,
)
from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import Investigation, Scope
from alert_triage.investigation.adapters.adk.agent import (
    Deployment,
    PlatformAccess,
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
from alert_triage.investigation.adapters.adk.guides import fetch_guides
from alert_triage.investigation.adapters.adk.investigator import run_agent
from alert_triage.investigation.adapters.adk.model import build_model
from alert_triage.investigation.adapters.crew.roster import CREW
from alert_triage.investigation.adapters.crew.specialists.logs import (
    LOGS_SPECIALIST,
)
from alert_triage.investigation.adapters.datadog.guides import DatadogGuide, guides_for
from alert_triage.investigation.adapters.datadog.links import (
    ITEM_KEYS,
    LOG_TOOLS,
    UNADDRESSED,
    DatadogLinks,
)
from alert_triage.investigation.adapters.datadog.mcp import (
    DATADOG,
    mcp_endpoint,
    mcp_headers,
)
from alert_triage.investigation.contract import InvestigationTarget, Section
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
    """Let the resolver decide whether API-key or enterprise auth can run."""
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
ENVIRONMENT = os.environ.get("ALERT_TRIAGE_LIVE_ENV", Scope.DEFAULT_ENV)
DECLARED_TOOLSETS = [
    (specialist.name, toolset) for specialist in CREW for toolset in specialist.toolsets
]


_log = logging.getLogger(__name__)


def _deployment() -> Deployment:
    """Use configured breakers and the guides a production run would offer."""
    return replace(_unguided_deployment(), guides=_guides())


@cache
def _guides() -> tuple[DatadogGuide, ...]:
    """Share the live guide listing; each published guide costs a call."""
    return fetch_guides(CREW, _unguided_deployment())


@cache
def _unguided_deployment() -> Deployment:
    connection = resolve_connection()
    breakers = load_config(DEFAULT_CONFIG_PATH).circuit_breakers
    model = build_model(Investigation.DEFAULT_MODEL, resolve_model_access())
    return Deployment(
        platforms={
            DATADOG: PlatformAccess(
                endpoint=mcp_endpoint(connection.site),
                headers=mcp_headers(
                    api_key=connection.api_key, app_key=connection.app_key
                ),
            )
        },
        model_for=lambda named: model,
        breakers=breakers,
    )


def _target() -> InvestigationTarget:
    fired_at = datetime.now(UTC) - timedelta(minutes=30)
    return InvestigationTarget(
        service=SERVICE,
        window=Window(start=fired_at, end=fired_at),
        alert_count=1,
        env=ENVIRONMENT,
    )


@pytest.mark.parametrize(
    ("specialist", "declared"),
    DECLARED_TOOLSETS,
    ids=[f"{name}-{toolset.name}" for name, toolset in DECLARED_TOOLSETS],
)
def test_every_declared_tool_exists_and_the_filter_admits_it(
    specialist: str, declared: Toolset
) -> None:
    """Only the real server can confirm these tool names."""
    toolset = McpToolset(
        connection_params=connection_for(declared, _deployment()),
        tool_filter=list(declared.tools),
    )

    tools = asyncio.run(toolset.get_tools())

    assert {tool.name for tool in tools} == set(declared.tools)


@pytest.mark.parametrize(
    "specialist", CREW, ids=[specialist.name for specialist in CREW]
)
def test_every_specialist_is_offered_a_guide_to_its_tools(
    specialist: Specialist,
) -> None:
    """The platform can reshape guide headings; no guide means guessing queries."""
    offered = guides_for(specialist, _deployment().guides)

    _log.info(
        "%s is offered %s",
        specialist.name,
        ", ".join(guide.name for guide in offered) or "nothing",
    )
    assert offered, f"{specialist.name} is offered no guide to its tools"


@pytest.mark.parametrize(
    "specialist", CREW, ids=[specialist.name for specialist in CREW]
)
def test_a_real_model_given_the_instruction_calls_them(specialist: Specialist) -> None:
    """A quiet service may find nothing, but it still has to retrieve."""
    retrieved = Retrieved()

    asyncio.run(
        run_agent(
            build_agent(specialist, _deployment(), retrieved), _target().describe()
        )
    )

    assert retrieved.retrievals >= 1
    assert retrieved.failures == ()


class _Recorded:
    """Pair each retrieval address with the tool that produced it."""

    def __init__(self, links: DatadogLinks) -> None:
        self._links = links
        self.addressed: list[tuple[str, str | None]] = []

    def to_retrieval(
        self,
        tool: str,
        args: Mapping[str, Any],
        service: str = "",
        env: str | None = None,
    ) -> str | None:
        address = self._links.to_retrieval(tool, args, service, env)
        self.addressed.append((tool, address))
        return address

    def to_item(
        self,
        tool: str,
        payload: Any,
        within: str | None,
        service: str = "",
        env: str | None = None,
    ) -> str | None:
        return self._links.to_item(tool, payload, within, service, env)

    def to_service(
        self,
        service: str,
        window: Window,
        section: Section | None,
        env: str | None = None,
    ) -> str | None:
        return self._links.to_service(service, window, section, env)


def _investigated(specialist: Specialist) -> tuple[Retrieved, _Recorded]:
    links = _Recorded(DatadogLinks(resolve_connection().web_host))
    retrieved = Retrieved(link=links, service=SERVICE, env=ENVIRONMENT)
    asyncio.run(
        run_agent(
            build_agent(specialist, _deployment(), retrieved),
            _target().describe(),
        )
    )
    return retrieved, links


@pytest.mark.parametrize(
    "specialist", CREW, ids=[specialist.name for specialist in CREW]
)
def test_each_retrieval_address_opens_rather_than_404s_or_is_absent(
    specialist: Specialist, answers: Callable[[str], bool]
) -> None:
    """Only Datadog can say whether an address template opens the right route."""
    retrieved, links = _investigated(specialist)

    assert retrieved.retrievals >= 1
    for tool, address in links.addressed:
        if tool in UNADDRESSED:
            assert address is None, f"{tool} was addressed at {address}"
        else:
            assert address is not None, f"{tool} was given no address"
            assert answers(address), f"the platform serves nothing at {address}"


@pytest.mark.parametrize("section", [None, *Section], ids=str)
def test_a_findings_service_page_opens_rather_than_404s(
    section: Section | None, answers: Callable[[str], bool]
) -> None:
    """Fragments never reach the server, so this only proves the page opens."""
    links = DatadogLinks(resolve_connection().web_host)

    address = links.to_service(SERVICE, _target().window, section, ENVIRONMENT)

    assert address is not None
    assert answers(address), f"the platform serves nothing at {address}"


def test_what_key_a_live_log_payload_identifies_an_item_by() -> None:
    """A missing item key is feedback for ITEM_KEYS, not a broken link."""
    retrieved, links = _investigated(LOGS_SPECIALIST)

    item = next(
        (
            retrieved.resolve(f"call-{call}/item-1")
            for call, (tool, _) in enumerate(links.addressed, start=1)
            if tool in LOG_TOOLS
        ),
        None,
    )
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
    """Only a live model proves the manager chooses and returns a valid report."""
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
