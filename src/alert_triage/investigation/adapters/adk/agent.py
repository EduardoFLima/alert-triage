"""MCP supplies tool signatures; deployment facts are injected here."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.bounds import Bounds
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
from alert_triage.investigation.adapters.adk.reasoning import log_reasoning
from alert_triage.investigation.adapters.adk.skills import guidance_for
from alert_triage.investigation.adapters.crew.reasoners.diagnostician import (
    diagnostician,
)
from alert_triage.investigation.adapters.datadog.guides import DatadogGuide
from alert_triage.investigation.domain.reasoner import Reasoner
from alert_triage.investigation.domain.specialist import Specialist, Toolset

if TYPE_CHECKING:
    from collections.abc import Sequence

    from google.adk.agents import LlmAgent
    from google.adk.models import BaseLlm
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

ModelFor = Callable[[str | None], "str | BaseLlm"]
"""Resolves each specialist's model choice with this deployment's credentials."""


@dataclass(frozen=True)
class PlatformAccess:
    endpoint: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class Deployment:
    platforms: Mapping[str, PlatformAccess]
    model_for: ModelFor
    breakers: CircuitBreakers = field(default_factory=CircuitBreakers)
    guides: tuple[DatadogGuide, ...] = ()


def connection_for(
    toolset: Toolset, deployment: Deployment
) -> "StreamableHTTPConnectionParams":
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    access = deployment.platforms.get(toolset.provider)
    if access is None:
        held = ", ".join(sorted(deployment.platforms)) or "none"
        raise KeyError(
            f"Toolset '{toolset.name}' names provider '{toolset.provider}', which "
            f"this deployment does not configure. Configured providers: {held}"
        )

    return StreamableHTTPConnectionParams(
        url=f"{access.endpoint}?toolsets={toolset.name}",
        headers=dict(access.headers),
        timeout=deployment.breakers.mcp_call_timeout_seconds,
        sse_read_timeout=deployment.breakers.mcp_call_timeout_seconds,
    )


def _permitted_tools(specialist: Specialist) -> frozenset[str]:
    return frozenset(tool for toolset in specialist.toolsets for tool in toolset.tools)


def build_agent(
    specialist: Specialist,
    deployment: Deployment,
    retrieved: Retrieved,
    bounds: Bounds | None = None,
) -> "LlmAgent":
    from google.adk.agents import LlmAgent
    from google.adk.agents.llm_agent import ToolUnion
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

    tools: list[ToolUnion] = [
        McpToolset(
            connection_params=connection_for(toolset, deployment),
            tool_filter=list(toolset.tools),
        )
        for toolset in specialist.toolsets
    ]
    guidance = guidance_for(specialist, deployment.guides)
    if guidance is not None:
        tools.append(guidance)
    within = bounds if bounds is not None else Bounds(deployment.breakers)
    return LlmAgent(
        name=specialist.name,
        model=deployment.model_for(specialist.model),
        instruction=specialist.instruction,
        output_schema=specialist.output_schema,
        tools=tools,
        before_tool_callback=log_tool_call(
            specialist.name, _permitted_tools(specialist), retrieved, within
        ),
        after_tool_callback=keep_evidence_callback(
            retrieved, _permitted_tools(specialist), specialist.name
        ),
    )


def build_reasoner(reasoner: Reasoner, deployment: Deployment) -> "LlmAgent":
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
    """Specialists stay AgentTools so the manager keeps one reasoning thread.

    ADK marks skip-summarized tool results final, so callbacks collect raw reports.
    """
    from google.adk.agents import LlmAgent
    from google.adk.tools.agent_tool import AgentTool

    manager = diagnostician(consulted.bounds.hops)
    return LlmAgent(
        name=manager.name,
        model=deployment.model_for(manager.model),
        instruction=manager.instruction,
        output_schema=manager.output_schema,
        tools=[
            AgentTool(
                agent=build_agent(specialist, deployment, retrieved, consulted.bounds)
            )
            for specialist in crew
        ],
        before_tool_callback=bound_consultations_callback(consulted),
        after_tool_callback=collect_findings_callback(consulted),
        on_tool_error_callback=failed_consultation_callback(consulted),
        after_model_callback=log_reasoning(manager.name),
    )
