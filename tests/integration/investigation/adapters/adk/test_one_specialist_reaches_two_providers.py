"""One declaration, two providers, one investigation.

The capability the slice exists for, proved where a fake cannot fake it: two
real MCP servers on two sockets, each with its own address and its own
credentials, and a single specialist whose toolsets name one each. What this
establishes past the unit tests is that the two connections really are separate
sessions — the agent does not open one and reuse it, and the header sent to one
provider is not the header the other authenticated with.

There is deliberately no assertion here about a specialist being *better* for
reaching two providers. It reaches them; whether asking two providers produces
a better investigation is the evaluation harness's question.
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
    """The provider a logs specialist has always had."""
    mcp = FastMCP("fake-observability")

    @mcp.tool(name=SEARCH_LOGS)
    def search(query: str) -> list[dict[str, str]]:
        """Return the log items matching a query."""
        return [{"timestamp": NOON.isoformat(), "message": "container OOMKilled"}]

    return mcp


def _deploy_history_server() -> FastMCP:
    """The second provider: what shipped, which no observability tool can say."""
    mcp = FastMCP("fake-deploy-history")

    @mcp.tool(name=LIST_DEPLOYS)
    def deploys(service: str) -> list[dict[str, str]]:
        """Return what was released for a service."""
        return [{"timestamp": NOON.isoformat(), "message": "checkout v4.2 released"}]

    return mcp


def _serve(app: Any, port: int) -> Iterator[str]:
    """Run one MCP server on a real socket for the duration of a test."""
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
        """Answer with the next turn the test wrote."""
        yield LlmResponse(content=self.turns.pop(0))


def _calls(name: str, **args: Any) -> types.Content:
    return types.Content(
        role="model",
        parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))],
    )


def _reports(cites: list[str]) -> types.Content:
    """One finding citing evidence retrieved from both providers."""
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
    """One declaration whose evidence comes from two providers."""
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
    """Two providers, each at its own address and behind its own credential."""
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
    """Drive the specialist through one call to each provider, then a report.

    Built and run the way a consultation would, rather than through a manager:
    the subject is one declaration's reach into two servers, and a manager
    deciding to ask is not what is in question.
    """
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


def test_a_specialist_gathers_evidence_from_both_providers_it_named(
    observability: str, deploy_history: str
) -> None:
    findings, _ = _investigation(observability, deploy_history)

    summaries = [
        item.summary for finding in findings.findings for item in finding.examples
    ]
    assert any("OOMKilled" in one for one in summaries)
    assert any("v4.2 released" in one for one in summaries)


def test_evidence_from_two_providers_is_citable_in_one_investigation(
    observability: str, deploy_history: str
) -> None:
    """Both retrievals land in the same record, so one finding may cite both."""
    _, retrieved = _investigation(observability, deploy_history)

    assert retrieved.resolve("call-1/item-1") is not None
    assert retrieved.resolve("call-2/item-1") is not None


def test_the_two_providers_are_reached_at_their_own_addresses(
    observability: str, deploy_history: str
) -> None:
    """Two sockets, not one: the second toolset is not served by the first server."""
    assert observability != deploy_history

    findings, _ = _investigation(observability, deploy_history)

    gathered = [item for finding in findings.findings for item in finding.examples]
    assert len(gathered) == 2
    assert findings.complete
