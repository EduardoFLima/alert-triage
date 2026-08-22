from typing import Any

import pytest
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from pydantic import BaseModel

from alert_triage.adapters.adk.evidence import Retrieved
from alert_triage.adapters.adk.specialists import (
    CONNECT_TIMEOUT_SECONDS,
    READ_TIMEOUT_SECONDS,
    Deployment,
    Specialist,
    Toolset,
    build_agent,
    connection_for,
)
from alert_triage.domain.findings import Signal


class _Reported(BaseModel):
    findings: list[str] = []


def _specialist(
    name: str = "logs_specialist",
    instruction: str = "Look at the logs and report what recurs.",
    model: str | None = None,
    toolsets: tuple[Toolset, ...] = (Toolset(name="core", tools=("search_logs",)),),
) -> Specialist:
    return Specialist(
        name=name,
        signal=Signal.LOGS,
        instruction=instruction,
        output_schema=_Reported,
        toolsets=toolsets,
        model=model,
    )


def _deployment(
    endpoint: str = "https://mcp.datadoghq.com/v1/mcp",
    headers: dict[str, str] | None = None,
    default: str = "a-default-model",
) -> Deployment:
    return Deployment(
        endpoint=endpoint,
        headers=headers or {"DD_API_KEY": "key", "DD_APPLICATION_KEY": "app"},
        model_for=lambda named: named or default,
    )


def _permitted(agent: Any) -> list[list[str]]:
    """The tool names each of an agent's toolsets exposes."""
    return [
        list(names)
        for toolset in agent.tools
        if isinstance(toolset, McpToolset)
        for names in [toolset.tool_filter]
        if isinstance(names, list)
    ]


def test_a_declaration_carries_everything_that_makes_a_specialist_itself() -> None:
    specialist = _specialist()

    assert specialist.name == "logs_specialist"
    assert specialist.signal is Signal.LOGS
    assert specialist.output_schema is _Reported
    assert specialist.toolsets[0].tools == ("search_logs",)
    assert specialist.model is None


def test_a_declaration_without_an_instruction_is_rejected() -> None:
    with pytest.raises(ValueError, match="instruction"):
        _specialist(instruction="   ")


def test_a_declaration_without_a_signal_is_rejected() -> None:
    with pytest.raises(ValueError, match="signal"):
        Specialist(
            name="logs_specialist",
            signal=None,  # type: ignore[arg-type]
            instruction="Look at the logs.",
            output_schema=_Reported,
            toolsets=(Toolset(name="core", tools=("search_logs",)),),
        )


def test_a_toolset_that_permits_no_tool_reaches_nothing_and_is_rejected() -> None:
    with pytest.raises(ValueError, match="tool"):
        Toolset(name="core", tools=())


def test_an_agent_is_built_from_the_declaration_and_nothing_else() -> None:
    agent = build_agent(_specialist(), _deployment(), Retrieved())

    assert agent.name == "logs_specialist"
    assert agent.instruction == "Look at the logs and report what recurs."
    assert agent.output_schema is _Reported


def test_the_toolset_is_filtered_to_the_tools_the_declaration_named() -> None:
    specialist = _specialist(
        toolsets=(Toolset(name="core", tools=("search_logs", "aggregate_logs")),)
    )

    agent = build_agent(specialist, _deployment(), Retrieved())

    assert _permitted(agent) == [["search_logs", "aggregate_logs"]]


def test_a_tool_the_declaration_did_not_name_is_not_among_the_ones_exposed() -> None:
    agent = build_agent(_specialist(), _deployment(), Retrieved())

    (permitted,) = _permitted(agent)
    assert "delete_dashboard" not in permitted


def test_the_endpoint_asks_the_platform_for_the_declared_toolsets() -> None:
    connection = connection_for(
        Toolset(name="core", tools=("search_logs",)), _deployment()
    )

    assert connection.url == "https://mcp.datadoghq.com/v1/mcp?toolsets=core"


def test_a_specialist_declaring_several_toolsets_gets_one_each() -> None:
    specialist = _specialist(
        toolsets=(
            Toolset(name="core", tools=("search_logs",)),
            Toolset(name="apm", tools=("list_spans",)),
        )
    )

    agent = build_agent(specialist, _deployment(), Retrieved())

    assert _permitted(agent) == [["search_logs"], ["list_spans"]]


def test_the_credentials_reach_the_connection_as_headers() -> None:
    connection = connection_for(
        Toolset(name="core", tools=("search_logs",)),
        _deployment(headers={"DD_API_KEY": "key", "DD_APPLICATION_KEY": "app"}),
    )

    assert connection.headers == {"DD_API_KEY": "key", "DD_APPLICATION_KEY": "app"}


def test_a_declaration_naming_no_model_reasons_on_the_default() -> None:
    agent = build_agent(
        _specialist(), _deployment(default="a-default-model"), Retrieved()
    )

    assert agent.model == "a-default-model"


def test_a_declaration_naming_its_own_model_beats_the_default() -> None:
    crew = (
        _specialist(name="logs_specialist"),
        _specialist(name="apm_specialist", model="a-bigger-model"),
    )
    deployment = _deployment(default="a-default-model")

    built = [build_agent(one, deployment, Retrieved()) for one in crew]

    assert [agent.model for agent in built] == ["a-default-model", "a-bigger-model"]


def test_the_same_declaration_is_unchanged_by_where_it_is_deployed() -> None:
    """Deployment facts are supplied to a declaration, never written into it."""
    specialist = _specialist()
    here = _deployment(
        endpoint="https://mcp.datadoghq.com/v1/mcp", headers={"DD_API_KEY": "one"}
    )
    there = _deployment(
        endpoint="https://mcp.datadoghq.eu/v1/mcp", headers={"DD_API_KEY": "two"}
    )

    build_agent(specialist, here, Retrieved())
    build_agent(specialist, there, Retrieved())

    assert specialist == _specialist()


def test_the_connection_bounds_are_set_rather_than_left_to_the_framework() -> None:
    """ADK's own defaults are 5s to connect and 300s to read; neither is our intent."""
    connection = connection_for(
        Toolset(name="core", tools=("search_logs",)), _deployment()
    )

    assert connection.timeout == CONNECT_TIMEOUT_SECONDS
    assert connection.sse_read_timeout == READ_TIMEOUT_SECONDS


def test_every_specialist_carries_the_evidence_callbacks() -> None:
    """The gate is registered per agent, closing over this investigation's evidence."""
    retrieved = Retrieved()

    agent = build_agent(_specialist(), _deployment(), retrieved)

    assert agent.after_tool_callback is not None
    assert agent.before_tool_callback is not None


def test_the_registered_callback_records_into_this_investigations_evidence() -> None:
    retrieved = Retrieved()
    agent = build_agent(_specialist(), _deployment(), retrieved)

    kept: Any = agent.after_tool_callback
    kept(
        tool=None,
        args={},
        tool_context=None,
        tool_response={"logs": [{"message": "OOMKilled"}]},
    )

    assert retrieved.resolve("call-1/item-1") is not None
