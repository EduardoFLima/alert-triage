"""A specialist is offered the platform's guides for its own tools, and no others.

The guides reach it through the framework's skill toolset: a menu of their
names and descriptions in its prompt, and a load for the text of one it
chooses. Nothing in its declaration changes, and nothing it loads is a
retrieval from the platform.
"""

import asyncio
from types import SimpleNamespace
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models.llm_request import LlmRequest
from google.adk.tools.skill_toolset import SkillToolset
from pydantic import BaseModel

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.agent import (
    Deployment,
    PlatformAccess,
    build_agent,
)
from alert_triage.investigation.adapters.adk.bounds import Bounds
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.datadog.guides import DatadogGuide
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset

METRICS_GUIDE = DatadogGuide(
    name="datadog/metrics",
    description="How a metric query is written.",
    text="# Metrics\n\n## Tools\n\n### get_datadog_metric\n\nAn aggregator first.",
    references={"references/functions.md": "rollup, as_count"},
)
LOGS_GUIDE = DatadogGuide(
    name="datadog/logs",
    description="How a log query is written.",
    text="# Logs\n\n## Tools\n\n### search_datadog_logs\n\nFacets start with @.",
)


class _Reported(BaseModel):
    findings: list[str] = []


def _specialist(*tools: str) -> Specialist:
    return Specialist(
        name="infrastructure_specialist",
        signal=Signal.INFRASTRUCTURE,
        instruction="Look at the metrics the service reports.",
        output_schema=_Reported,
        toolsets=(Toolset(provider="datadog", name="core", tools=tools),),
    )


def _deployment(*guides: DatadogGuide, calls: int = 10) -> Deployment:
    return Deployment(
        platforms={
            "datadog": PlatformAccess(
                endpoint="https://mcp.datadoghq.com/v1/mcp",
                headers={"DD_API_KEY": "key"},
            )
        },
        model_for=lambda named: named or "a-default-model",
        breakers=CircuitBreakers(max_tool_calls_per_agent=calls),
        guides=guides,
    )


def _built(
    specialist: Specialist,
    deployment: Deployment,
    retrieved: Retrieved | None = None,
    bounds: Bounds | None = None,
) -> LlmAgent:
    return build_agent(specialist, deployment, retrieved or Retrieved(), bounds)


def _skill_toolsets(agent: LlmAgent) -> list[SkillToolset]:
    return [tool for tool in agent.tools if isinstance(tool, SkillToolset)]


def _guidance(agent: LlmAgent) -> SkillToolset:
    (toolset,) = _skill_toolsets(agent)
    return toolset


NO_CONTEXT: Any = SimpleNamespace()
"""A call's context, which offering the menu never reads."""

METRICS_SPECIALIST = _specialist("get_datadog_metric")
GUIDED = _deployment(METRICS_GUIDE, LOGS_GUIDE)


def test_a_specialist_holds_only_the_guides_for_its_own_tools() -> None:
    guidance = _guidance(_built(METRICS_SPECIALIST, GUIDED))

    assert [skill.name for skill in guidance.skills] == ["datadog-metrics"]


def test_it_may_only_load_a_guide_or_one_of_its_references() -> None:
    """Listing is left out: the menu is in its prompt, and a script is not ours."""
    guidance = _guidance(_built(METRICS_SPECIALIST, GUIDED))

    assert {tool.name for tool in asyncio.run(guidance.get_tools())} == {
        "load_skill",
        "load_skill_resource",
    }


def test_the_guides_it_holds_are_named_and_described_in_its_prompt() -> None:
    request = LlmRequest()

    asyncio.run(
        _guidance(_built(METRICS_SPECIALIST, GUIDED)).process_llm_request(
            tool_context=NO_CONTEXT, llm_request=request
        )
    )

    prompt = str(request.config.system_instruction)
    assert "datadog-metrics" in prompt
    assert METRICS_GUIDE.description in prompt
    assert "datadog-logs" not in prompt
    assert "An aggregator first." not in prompt
