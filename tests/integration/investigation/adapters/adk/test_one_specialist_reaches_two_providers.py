"""Prove two toolsets open separate MCP sessions with their own credentials."""

import asyncio
import threading
import time
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
import uvicorn
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from alert_triage.investigation.adapters.adk.agent import (
    Deployment,
    PlatformAccess,
    build_agent,
)
from alert_triage.investigation.adapters.adk.consultation import Consulted
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.adk.investigator import run_agent
from alert_triage.investigation.adapters.crew.specialists.logs import ReportedFindings
from alert_triage.investigation.contract import (
    Findings,
    InvestigationTarget,
    Signal,
)
from alert_triage.investigation.domain.specialist import Specialist, Toolset
from alert_triage.shared.window import Window

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

OBSERVABILITY = "observability"
DEPLOY_HISTORY = "deploy_history"

SEARCH_LOGS = "search_logs"
LIST_DEPLOYS = "list_deploys"

seen_headers: dict[str, dict[str, str]] = {}


def _observability_server() -> FastMCP:
    mcp = FastMCP("fake-observability")

    @mcp.tool(name=SEARCH_LOGS)
    def search(query: str) -> list[dict[str, str]]:
        """Return the log items matching a query."""
        return [{"timestamp": NOON.isoformat(), "message": "container OOMKilled"}]

    return mcp


def _deploy_history_server() -> FastMCP:
    mcp = FastMCP("fake-deploy-history")

    @mcp.tool(name=LIST_DEPLOYS)
    def deploys(service: str) -> list[dict[str, str]]:
        """Return what was released for a service."""
        return [{"timestamp": NOON.isoformat(), "message": "checkout v4.2 released"}]

    return mcp


def _serve(app: Any, port: int) -> Iterator[str]:
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        if not thread.is_alive():
            pytest.fail("a fake MCP server did not start")
        time.sleep(0.01)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def observability(free_ports: tuple[int, int]) -> Iterator[str]:
    yield from _serve(_observability_server().streamable_http_app(), free_ports[0])


@pytest.fixture
def deploy_history(free_ports: tuple[int, int]) -> Iterator[str]:
    yield from _serve(_deploy_history_server().streamable_http_app(), free_ports[1])


class _ScriptedModel(BaseLlm):
    """The one thing standing in: a model whose turns a test writes out."""

    turns: list[types.Content] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse]:
        yield LlmResponse(content=self.turns.pop(0))


def _calls(name: str, **args: Any) -> types.Content:
    return types.Content(
        role="model",
        parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))],
    )


def _reports(cites: list[str]) -> types.Content:
    cited = ", ".join(f'"{one}"' for one in cites)
    return types.Content(
        role="model",
        parts=[
            types.Part(
                text=(
                    '{"findings": [{"observation": "OOMKilled follows the release", '
                    f'"occurrences": 1, "cites": [{cited}]}}]}}'
                )
            )
        ],
    )


def _specialist() -> Specialist:
    return Specialist(
        name="apm_specialist",
        signal=Signal.APM,
        instruction="Search the logs, then check what deployed around them.",
        output_schema=ReportedFindings,
        toolsets=(
            Toolset(provider=OBSERVABILITY, name="core", tools=(SEARCH_LOGS,)),
            Toolset(provider=DEPLOY_HISTORY, name="releases", tools=(LIST_DEPLOYS,)),
        ),
    )


def _deployment(observability: str, deploy_history: str, model: BaseLlm) -> Deployment:
    return Deployment(
        platforms={
            OBSERVABILITY: PlatformAccess(
                endpoint=observability, headers={"DD_API_KEY": "observability-key"}
            ),
            DEPLOY_HISTORY: PlatformAccess(
                endpoint=deploy_history, headers={"AUTHORIZATION": "Bearer deploy-key"}
            ),
        },
        model_for=lambda named: model,
    )


def _target() -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout", window=Window(start=NOON, end=NOON), alert_count=1
    )


def _investigation(observability: str, deploy_history: str) -> Any:
    """Run one declaration directly; manager routing is out of scope."""
    model = _ScriptedModel(
        model="scripted",
        turns=[
            _calls(SEARCH_LOGS, query="service:checkout"),
            _calls(LIST_DEPLOYS, service="checkout"),
            _reports(["call-1/item-1", "call-2/item-1"]),
        ],
    )
    retrieved = Retrieved()
    specialist = _specialist()
    consulted = Consulted(offered=(specialist,), retrieved=retrieved)
    reported = asyncio.run(
        run_agent(
            build_agent(
                specialist,
                _deployment(observability, deploy_history, model),
                retrieved,
            ),
            _target().describe(),
        )
    )
    consulted.record(specialist, reported)
    return Findings(
        findings=consulted.findings,
        retrieval_failures=retrieved.failures,
        consulted=consulted.signals,
    ), retrieved


def test_a_specialist_reaches_both_providers_and_cites_their_evidence(
    observability: str, deploy_history: str
) -> None:
    """Two sockets, not one: the second toolset is not served by the first server."""
    assert observability != deploy_history

    findings, retrieved = _investigation(observability, deploy_history)

    gathered = [item for finding in findings.findings for item in finding.examples]
    assert len(gathered) == 2
    assert any("OOMKilled" in item.summary for item in gathered)
    assert any("v4.2 released" in item.summary for item in gathered)
    assert retrieved.resolve("call-1/item-1") is not None
    assert retrieved.resolve("call-2/item-1") is not None
    assert findings.complete
