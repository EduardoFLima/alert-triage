"""A specialist against a real MCP server, with no network and no model.

The unit tests drive the callback with canned tool results, which is what makes
them fast — and also what would let a wrong assumption about ADK's tool path
pass them. This is the test that would catch it: a real ``McpToolset`` connects
to a real MCP server over a real socket, a real ADK runner calls its tools, and
the model is the only thing standing in.

What it proves that a fake cannot: that the tool filter is applied, that a
successful result reaches the model as citable evidence, and that a failing
tool reaches it as a refusal rather than as an empty answer.
"""

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
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.genai import types
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from alert_triage.investigation.adapters.adk.agent import (
    Deployment,
    PlatformAccess,
    build_agent,
    connection_for,
)
from alert_triage.investigation.adapters.adk.consultation import Consulted
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.adk.investigator import run_agent
from alert_triage.investigation.adapters.crew.specialists.logs import (
    ReportedFindings,
)
from alert_triage.investigation.contract import (
    Findings,
    InvestigationTarget,
    Signal,
)
from alert_triage.investigation.domain.evidence import RETRIEVAL_FAILED
from alert_triage.investigation.domain.specialist import Specialist, Toolset
from alert_triage.investigation.ports.investigator import InvestigatorError
from alert_triage.shared.window import Window

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

SEARCH = "search_datadog_logs"
AGGREGATE = "aggregate_datadog_logs"
FORBIDDEN = "delete_datadog_dashboard"


def _server() -> FastMCP:
    """A platform offering three tools, one of which nothing may reach."""
    mcp = FastMCP("fake-platform")

    @mcp.tool(name=SEARCH)
    def search(query: str) -> list[dict[str, str]]:
        """Return the log items matching a query."""
        return [
            {"timestamp": NOON.isoformat(), "message": "container OOMKilled"},
            {"timestamp": NOON.isoformat(), "message": "restarting checkout"},
        ]

    @mcp.tool(name=AGGREGATE)
    def aggregate(query: str) -> dict[str, int]:
        """Fail, as a platform refusing a malformed query would."""
        raise ValueError("the query could not be parsed")

    @mcp.tool(name=FORBIDDEN)
    def forbidden() -> str:
        """Exist, so that the filter has something to keep out."""
        return "deleted"

    return mcp


@pytest.fixture
def platform(free_port: int) -> Iterator[str]:
    """The fake platform, served over a real socket for the duration of a test."""
    server = uvicorn.Server(
        uvicorn.Config(
            _server().streamable_http_app(),
            host="127.0.0.1",
            port=free_port,
            log_level="error",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        if not thread.is_alive():
            pytest.fail("the fake MCP server did not start")
        time.sleep(0.01)
    yield f"http://127.0.0.1:{free_port}/mcp"
    server.should_exit = True
    thread.join(timeout=10)


def _specialist() -> Specialist:
    return Specialist(
        name="logs_specialist",
        signal=Signal.LOGS,
        instruction="Search the logs and report what recurs.",
        output_schema=ReportedFindings,
        toolsets=(Toolset(provider="datadog", name="core", tools=(SEARCH, AGGREGATE)),),
    )


def _target() -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout",
        window=Window(start=NOON, end=NOON),
        alert_count=1,
    )


class _ScriptedModel(BaseLlm):
    """The one thing standing in: a model whose turns a test writes out."""

    turns: list[types.Content] = Field(default_factory=list)
    seen: list[LlmRequest] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse]:
        """Answer with the next turn the test wrote, remembering what it was given."""
        self.seen.append(llm_request)
        yield LlmResponse(content=self.turns.pop(0))


def _calls(name: str, **args: Any) -> types.Content:
    return types.Content(
        role="model",
        parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))],
    )


def _reports(cites: list[str]) -> types.Content:
    findings = ", ".join(f'"{one}"' for one in cites)
    return types.Content(
        role="model",
        parts=[
            types.Part(
                text=(
                    '{"findings": [{"observation": "OOMKilled recurs", '
                    f'"occurrences": 2, "cites": [{findings}]}}]}}'
                )
            )
        ],
    )


def _deployment(platform: str, model: BaseLlm) -> Deployment:
    return Deployment(
        platforms={
            "datadog": PlatformAccess(
                endpoint=platform,
                headers={"DD_API_KEY": "api", "DD_APPLICATION_KEY": "app"},
            )
        },
        model_for=lambda named: model,
    )


def _investigate(platform: str, model: _ScriptedModel) -> Any:
    """One specialist over one platform, driven the way a consultation drives it.

    The manager is not the subject here — the specialist's reach into a real MCP
    server is. So this builds the agent a consultation would build and runs it,
    rather than paying for a manager to decide to.
    """
    retrieved = Retrieved()
    consulted = Consulted(offered=(_specialist(),), retrieved=retrieved)
    reported = asyncio.run(
        run_agent(
            build_agent(_specialist(), _deployment(platform, model), retrieved),
            _target().describe(),
        )
    )
    consulted.record(_specialist(), reported)
    if retrieved.failures and not retrieved.retrievals:
        raise InvestigatorError(
            f"No evidence could be gathered: {'; '.join(retrieved.failures)}"
        )
    return Findings(
        findings=consulted.findings,
        retrieval_failures=retrieved.failures,
        consulted=consulted.signals,
    )


def test_the_toolset_exposes_only_the_tools_the_declaration_named(
    platform: str,
) -> None:
    toolset = McpToolset(
        connection_params=connection_for(
            Toolset(provider="datadog", name="core", tools=(SEARCH,)),
            _deployment(platform, _ScriptedModel(model="scripted")),
        ),
        tool_filter=[SEARCH],
    )

    tools = asyncio.run(toolset.get_tools())

    assert [tool.name for tool in tools] == [SEARCH]


def test_a_specialist_gathers_evidence_it_can_then_cite(platform: str) -> None:
    model = _ScriptedModel(
        model="scripted",
        turns=[
            _calls(SEARCH, query="service:checkout status:error"),
            _reports(["call-1/item-1"]),
        ],
    )

    findings = _investigate(platform, model)

    (finding,) = findings.findings
    assert finding.examples[0].summary == "container OOMKilled"
    assert findings.complete


def test_a_failing_tool_reaches_the_model_as_a_refusal_not_an_empty_answer(
    platform: str,
) -> None:
    """The gate, through the real tool path rather than through the callback alone."""
    model = _ScriptedModel(
        model="scripted",
        turns=[
            _calls(AGGREGATE, query="service:checkout"),
            _calls(SEARCH, query="service:checkout status:error"),
            _reports(["call-1/item-1"]),
        ],
    )

    findings = _investigate(platform, model)

    assert RETRIEVAL_FAILED in str(model.seen[-1].contents)
    assert not findings.complete
    assert AGGREGATE in findings.retrieval_failures[0]


def test_an_investigation_that_could_reach_nothing_is_a_failure(
    platform: str,
) -> None:
    model = _ScriptedModel(
        model="scripted",
        turns=[_calls(AGGREGATE, query="service:checkout"), _reports(["call-1"])],
    )

    with pytest.raises(InvestigatorError, match=AGGREGATE):
        _investigate(platform, model)


def test_a_tool_outside_the_declaration_is_not_reachable(platform: str) -> None:
    """The platform offers it; the specialist cannot see it, so it cannot call it."""
    model = _ScriptedModel(
        model="scripted",
        turns=[
            _calls(SEARCH, query="service:checkout"),
            _reports(["call-1/item-1"]),
        ],
    )

    _investigate(platform, model)

    offered = {
        tool.name
        for request in model.seen
        for tool in (request.config.tools or [])
        for tool in getattr(tool, "function_declarations", None) or []
    }
    assert SEARCH in offered
    assert FORBIDDEN not in offered
