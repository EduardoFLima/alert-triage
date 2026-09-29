import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
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

METRICS_SPECIALIST = _specialist("get_datadog_metric")
GUIDED = _deployment(METRICS_GUIDE, LOGS_GUIDE)


def test_a_specialist_holds_only_the_guides_for_its_own_tools() -> None:
    guidance = _guidance(_built(METRICS_SPECIALIST, GUIDED))

    assert [skill.name for skill in guidance.skills] == ["datadog-metrics"]


def test_it_may_only_load_a_guide_or_one_of_its_references() -> None:
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


def test_its_instruction_is_its_declarations_and_holds_no_guide() -> None:
    agent = _built(METRICS_SPECIALIST, GUIDED)

    assert agent.instruction == METRICS_SPECIALIST.instruction
    assert "An aggregator first." not in str(agent.instruction)


def _load(agent: LlmAgent, tool: str, **args: str) -> Any:
    (loader,) = [
        loaded
        for loaded in asyncio.run(_guidance(agent).get_tools())
        if loaded.name == tool
    ]
    context: Any = SimpleNamespace(
        invocation_id="an-investigation", agent_name="infrastructure", state={}
    )
    return asyncio.run(loader.run_async(args=args, tool_context=context))


def test_an_offered_guide_is_given_when_asked_for() -> None:
    loaded = _load(
        _built(METRICS_SPECIALIST, GUIDED), "load_skill", skill_name="datadog-metrics"
    )

    assert loaded["instructions"] == METRICS_GUIDE.text


def test_a_reference_of_an_offered_guide_is_given_by_its_path() -> None:
    loaded = _load(
        _built(METRICS_SPECIALIST, GUIDED),
        "load_skill_resource",
        skill_name="datadog-metrics",
        file_path="references/functions.md",
    )

    assert loaded["content"] == "rollup, as_count"


def test_a_guide_it_was_not_offered_is_refused_by_name() -> None:
    loaded = _load(
        _built(METRICS_SPECIALIST, GUIDED), "load_skill", skill_name="datadog-logs"
    )

    assert loaded["error_code"] == "SKILL_NOT_FOUND"


class _Named:
    def __init__(self, name: str) -> None:
        self.name = name


def _through_callbacks(agent: LlmAgent, tool: str, response: Any) -> Any:
    before: Any = agent.before_tool_callback
    after: Any = agent.after_tool_callback
    args = {"skill_name": "datadog-metrics"}
    declined = before(tool=_Named(tool), args=args, tool_context=None)
    if declined is not None:
        return declined
    return after(
        tool=_Named(tool), args=args, tool_context=None, tool_response=response
    )


def test_loading_a_guide_spends_none_of_its_budget_and_is_not_evidence() -> None:
    deployment = _deployment(METRICS_GUIDE, calls=1)
    retrieved, bounds = Retrieved(), Bounds(deployment.breakers)
    agent = _built(METRICS_SPECIALIST, deployment, retrieved, bounds)

    for _ in range(3):
        assert (
            _through_callbacks(agent, "load_skill", {"instructions": "grammar"}) is None
        )

    assert retrieved.retrievals == 0
    assert retrieved.failures == ()
    assert (
        _through_callbacks(agent, "get_datadog_metric", {"series": [1.0]}) is not None
    ), "the one call its budget allows is still there to spend, and kept"
    assert retrieved.retrievals == 1


def test_a_refused_load_does_not_mark_the_investigation_incomplete() -> None:
    retrieved = Retrieved()
    agent = _built(METRICS_SPECIALIST, GUIDED, retrieved)

    _through_callbacks(
        agent,
        "load_skill",
        {"error": "Skill 'datadog-logs' not found.", "error_code": "SKILL_NOT_FOUND"},
    )

    assert retrieved.failures == ()


@pytest.mark.parametrize(
    "deployment",
    (_deployment(LOGS_GUIDE), _deployment()),
    ids=("none-documents-its-tools", "none-were-read"),
)
def test_a_specialist_offered_no_guide_is_told_of_no_skills(
    deployment: Deployment,
) -> None:
    assert _skill_toolsets(_built(METRICS_SPECIALIST, deployment)) == []
