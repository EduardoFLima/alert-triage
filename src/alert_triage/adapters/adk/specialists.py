"""What a specialist is, and how one becomes an agent.

A specialist is data. Its name, the signal it reports under, what it is
instructed to look for, the shape of what it reports, the tools it may reach,
and — where it differs from its siblings — the model it reasons on are one
value, declared in one place. Adding a specialist is adding a declaration;
widening what one may ask is a word in a tuple.

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
from typing import TYPE_CHECKING, Any

from alert_triage.adapters.adk.evidence import Retrieved, calls_logged, evidence_kept
from alert_triage.domain.findings import Signal

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


@dataclass(frozen=True)
class Toolset:
    """A group of tools on the platform, and which of them a specialist may reach.

    Both halves are needed and they bound different things: the platform is
    asked for the group, and the framework is told the names within it. Only
    the second is ours to enforce if the platform regroups its tools.

    Attributes:
        name: The toolset as the platform groups it.
        tools: The tools within it this specialist is permitted to call.
    """

    name: str
    tools: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject a toolset that reaches nothing, which is a silent specialist."""
        if not self.name.strip():
            raise ValueError("A toolset needs the name the platform groups it under")
        if not self.tools:
            raise ValueError(
                "A toolset naming no tools permits nothing: name what may be called"
            )


@dataclass(frozen=True)
class Specialist:
    """One specialist, declared whole.

    Attributes:
        name: What this specialist is called, in the agent and in configuration.
        signal: The observability dimension its findings are drawn from.
        instruction: What it is asked to look for, in the terms of the platform
            it queries. Platform-specific by necessity: a query dialect does
            not translate, and pretending otherwise is what this slice undid.
        output_schema: The shape it reports in. It has no free-text evidence
            field; it cites what it was shown.
        toolsets: What it may reach, and nothing else.
        model: The model it reasons on, or ``None`` to take the deployment's
            default.
    """

    name: str
    signal: Signal
    instruction: str
    output_schema: type[Any]
    toolsets: tuple[Toolset, ...]
    model: str | None = None

    def __post_init__(self) -> None:
        """Reject a declaration that could not run as one."""
        if not self.name.strip():
            raise ValueError(
                "A specialist needs a name to be configured and reported by"
            )
        if not isinstance(self.signal, Signal):
            raise ValueError(
                "A specialist needs the signal its findings are drawn from"
            )
        if not self.instruction.strip():
            raise ValueError(
                "A specialist needs an instruction: without one it looks for nothing"
            )
        if not self.toolsets:
            raise ValueError("A specialist with no toolsets can gather no evidence")


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


def _permitted(specialist: Specialist) -> frozenset[str]:
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
        before_tool_callback=calls_logged(),
        after_tool_callback=evidence_kept(retrieved, _permitted(specialist)),
    )
