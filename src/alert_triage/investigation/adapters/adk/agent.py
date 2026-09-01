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

from alert_triage.investigation.adapters.adk.consultation import (
    Consulted,
    bound_consultations_callback,
    collect_findings_callback,
    failed_consultation_callback,
)
from alert_triage.investigation.adapters.adk.evidence import (
    Retrieved,
    keep_evidence_callback,
    log_tool_call,
)
from alert_triage.investigation.adapters.adk.reasoners.diagnostician import (
    DIAGNOSTICIAN,
)
from alert_triage.investigation.adapters.adk.reasoning import log_reasoning
from alert_triage.investigation.domain.reasoner import Reasoner
from alert_triage.investigation.domain.specialist import Specialist, Toolset

if TYPE_CHECKING:
    from collections.abc import Sequence

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
        before_tool_callback=log_tool_call(specialist.name),
        after_tool_callback=keep_evidence_callback(
            retrieved, _permitted_tools(specialist), specialist.name
        ),
    )


def build_reasoner(reasoner: Reasoner, deployment: Deployment) -> "LlmAgent":
    """Build an agent that reasons over what it is given and reaches nothing.

    Args:
        reasoner: What to build.
        deployment: What it reasons on when it names no model of its own.

    Returns:
        The agent, with no tools: it is given everything it needs in its prompt.
        Its one callback writes down what it said, which for an agent that
        reaches nothing is the whole of its contribution.
    """
    from google.adk.agents import LlmAgent

    return LlmAgent(
        name=reasoner.name,
        model=deployment.model_for(reasoner.model),
        instruction=reasoner.instruction,
        output_schema=reasoner.output_schema,
        after_model_callback=log_reasoning(reasoner.name),
    )


def build_manager(
    crew: "Sequence[Specialist]",
    deployment: Deployment,
    consulted: Consulted,
    retrieved: Retrieved,
) -> "LlmAgent":
    """Build the Diagnostician over the crew it may consult.

    Each specialist is wrapped as a tool rather than made a sub-agent to hand
    off to. Handing off would give the specialist the conversation and take from
    the manager the thread it is reasoning on, which is the one thing it exists
    to keep. As tools, the specialists answer and the manager decides what to
    ask next.

    Their summarisation is deliberately not skipped. Skipping it sets
    ``skip_summarization`` on the consultation's result, which ``is_final_response``
    reports as final, which ends the manager's turn — the framework's loop runs
    ``while True`` until the last event is final. A manager whose turn ends on
    its first answer cannot consult a second specialist, cannot reason across
    what came back, and cannot produce its schema at all. Asking for the raw
    answer that way costs the whole conversation, and buys nothing: the report
    is collected in ``after_tool_callback``, before anything the model does with
    it.

    Its three callbacks are the ones a manager needs and a specialist does not.
    One bounds how many questions this incident may cost. One keeps each
    specialist's report — checked — before the manager reads it. One writes
    down what it said between the two, which is the only account of why it asked
    what it asked. And one keeps a
    specialist's failure to that specialist: unhandled, a tool error re-raises
    and ends the investigation, so one agent answering in prose where its schema
    was asked for would cost every other agent's work. The manager reaches no
    platform of its own, so none of the three contends with the evidence
    callbacks its specialists carry.

    Args:
        crew: The specialists to offer, every one of them.
        deployment: Where their platform is, how to authenticate, and what an
            agent reasons on when it names no model of its own.
        consulted: This investigation's record of what was asked.
        retrieved: This investigation's evidence, which the specialists' own
            callbacks close over.

    Returns:
        The manager, reaching its specialists and nothing else.
    """
    from google.adk.agents import LlmAgent
    from google.adk.tools.agent_tool import AgentTool

    return LlmAgent(
        name=DIAGNOSTICIAN.name,
        model=deployment.model_for(DIAGNOSTICIAN.model),
        instruction=DIAGNOSTICIAN.instruction,
        output_schema=DIAGNOSTICIAN.output_schema,
        tools=[
            AgentTool(agent=build_agent(specialist, deployment, retrieved))
            for specialist in crew
        ],
        before_tool_callback=bound_consultations_callback(consulted),
        after_tool_callback=collect_findings_callback(consulted),
        on_tool_error_callback=failed_consultation_callback(consulted),
        after_model_callback=log_reasoning(DIAGNOSTICIAN.name),
    )
