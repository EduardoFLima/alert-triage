"""How a declaration becomes an agent this framework can run.

The coordinator that builds an agent from a declaration learns no tool
signature and no query dialect. That is what makes the crew extensible without
it changing: the model discovers what its tools take at runtime, from the
platform's own MCP server, and the instruction that tells it what to look for
travels with the declaration rather than with the machinery.

Deployment facts — where the platform is, how to authenticate, and what model
a specialist reasons on unless it says otherwise — are supplied here rather
than declared. The same declaration runs against two accounts unchanged, which
is the property that keeps a contributor's specialist portable.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from alert_triage.investigation.adapters.adk.evidence import (
    Retrieved,
    log_tool_call,
    keep_evidence_callback,
)
from alert_triage.investigation.domain.specialist import Specialist, Toolset

if TYPE_CHECKING:
    from google.adk.agents import LlmAgent
    from google.adk.models import BaseLlm
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

CONNECT_TIMEOUT_SECONDS = 30.0
READ_TIMEOUT_SECONDS = 30.0
"""What the vision's ``mcp_call_timeout_seconds`` means now that ADK owns the client.

Set explicitly, and beside each other, so ADK's own defaults — five seconds to
connect and five minutes to read — cannot apply by accident to a bound this
project states as thirty seconds. Reading them from configuration is slice
12's work; stating them is this slice's.
"""


ModelFor = Callable[[str | None], "str | BaseLlm"]
"""How a deployment turns what a specialist asked for into a model it can run.

A function rather than a model, because a specialist naming its own model must
reach it already told how to authenticate — and where that credential comes
from is the composition root's business, not a declaration's.
"""


@dataclass(frozen=True)
class Deployment:
    """Where this deployment's platform is, and what it reasons with.

    Attributes:
        endpoint: The platform's MCP server, without the toolsets it is asked
            for: each declaration asks for its own.
        headers: What the server authenticates a request with.
        model_for: The model a specialist reasons on, given what it asked for.
    """

    endpoint: str
    headers: Mapping[str, str]
    model_for: ModelFor


def connection_for(
    toolset: Toolset, deployment: Deployment
) -> "StreamableHTTPConnectionParams":
    """How to reach one toolset on this deployment's platform.

    Args:
        toolset: The group of tools to ask the platform for.
        deployment: Where the platform is and how to authenticate.

    Returns:
        The connection parameters, bounded explicitly rather than by default.
    """
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    return StreamableHTTPConnectionParams(
        url=f"{deployment.endpoint}?toolsets={toolset.name}",
        headers=dict(deployment.headers),
        timeout=CONNECT_TIMEOUT_SECONDS,
        sse_read_timeout=READ_TIMEOUT_SECONDS,
    )


def _permitted_tools(specialist: Specialist) -> frozenset[str]:
    """Every tool this specialist declared, across all its toolsets."""
    return frozenset(tool for toolset in specialist.toolsets for tool in toolset.tools)


def build_agent(
    specialist: Specialist, deployment: Deployment, retrieved: Retrieved
) -> "LlmAgent":
    """Build the agent one declaration describes, for one investigation.

    Args:
        specialist: What to build.
        deployment: Where its platform is, how to authenticate, and what it
            reasons on when it names no model of its own.
        retrieved: This investigation's evidence, which the callbacks close
            over so that citations are scoped to this incident.

    Returns:
        The agent, reaching the tools its declaration named and no others.
    """
    from google.adk.agents import LlmAgent
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

    return LlmAgent(
        name=specialist.name,
        model=deployment.model_for(specialist.model),
        instruction=specialist.instruction,
        output_schema=specialist.output_schema,
        tools=[
            McpToolset(
                connection_params=connection_for(toolset, deployment),
                tool_filter=list(toolset.tools),
            )
            for toolset in specialist.toolsets
        ],
        before_tool_callback=log_tool_call(),
        after_tool_callback=keep_evidence_callback(retrieved, _permitted_tools(specialist)),
    )
