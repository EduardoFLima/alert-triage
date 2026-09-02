"""The manager reaches its specialists, and nothing else.

An agent whose tools are agents is the shape this slice turns on, and the two
things worth asserting about it are that every specialist is reachable and that
the manager itself holds no platform toolset — it asks, it does not search.
"""

from typing import Any

from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.agent import (
    Deployment,
    build_agent,
    build_manager,
    build_reasoner,
)
from alert_triage.investigation.adapters.adk.consultation import Consulted
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.crew.reasoners.diagnostician import (
    DIAGNOSTICIAN,
)
from alert_triage.investigation.adapters.crew.reasoners.report import REPORT_WRITER
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset


class _Reported(BaseModel):
    findings: list[dict[str, Any]] = []


def _specialist(name: str, signal: Signal) -> Specialist:
    return Specialist(
        name=name,
        signal=signal,
        instruction="Look.",
        output_schema=_Reported,
        toolsets=(
            Toolset(provider="datadog", name="core", tools=("search_datadog_logs",)),
        ),
    )


CREW = (
    _specialist("logs_specialist", Signal.LOGS),
    _specialist("apm_specialist", Signal.APM),
)


def _deployment() -> Deployment:
    return Deployment(
        endpoint="https://mcp.example/api",
        headers={"DD-API-KEY": "key"},
        model_for=lambda named: named or "gemini-2.5-flash",
    )


def _manager() -> Any:
    retrieved = Retrieved()
    return build_manager(
        CREW,
        _deployment(),
        Consulted(offered=CREW, retrieved=retrieved),
        retrieved,
    )


def test_the_manager_reaches_one_tool_per_specialist() -> None:
    tools = _manager().tools

    assert len(tools) == len(CREW)
    assert all(isinstance(tool, AgentTool) for tool in tools)


def test_each_tool_is_named_for_the_specialist_it_reaches() -> None:
    """The tool name is what the consultation callbacks key on."""
    named = {tool.agent.name for tool in _manager().tools}

    assert named == {"logs_specialist", "apm_specialist"}


def test_the_manager_holds_no_toolset_of_its_own() -> None:
    """It asks specialists; searching the platform is what they are for."""
    assert not any(isinstance(tool, McpToolset) for tool in _manager().tools)


def test_the_manager_carries_the_consultation_callbacks() -> None:
    manager = _manager()

    assert manager.before_tool_callback is not None
    assert manager.after_tool_callback is not None


def test_the_manager_carries_the_reasoning_log() -> None:
    """Why it asked what it asked lives in its own words, and nowhere else."""
    assert _manager().after_model_callback is not None


def test_a_specialist_carries_no_reasoning_log() -> None:
    """A specialist reports through a schema; the manager is the one reasoning."""
    agent = build_agent(CREW[0], _deployment(), Retrieved())

    assert agent.after_model_callback is None


def test_the_manager_is_the_diagnostician_declaration() -> None:
    manager = _manager()

    assert manager.name == DIAGNOSTICIAN.name
    assert manager.instruction == DIAGNOSTICIAN.instruction


def test_a_reasoner_is_built_with_no_tools_at_all() -> None:
    """The report agent is given everything it needs; it reaches nothing."""
    agent = build_reasoner(REPORT_WRITER, _deployment())

    assert agent.tools == []
    assert agent.name == "report_writer"


def test_a_reasoner_carries_the_reasoning_log() -> None:
    """The report agent's turn is the report taking shape; nothing else keeps it."""
    assert build_reasoner(REPORT_WRITER, _deployment()).after_model_callback is not None


def test_a_reasoner_takes_the_deployments_model() -> None:
    agent = build_reasoner(REPORT_WRITER, _deployment())

    assert agent.model == "gemini-2.5-flash"


def test_the_manager_answers_a_failed_consultation_rather_than_letting_it_raise() -> (
    None
):
    """Unhandled, a tool error ends the run and takes every finding with it."""
    manager = _manager()

    assert manager.on_tool_error_callback is not None
