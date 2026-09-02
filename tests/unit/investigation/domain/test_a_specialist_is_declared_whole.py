"""A specialist is data: everything that makes one is in its declaration.

A declaration that could not run as one is rejected where it is written rather
than when an agent is built from it.
"""

import pytest
from pydantic import BaseModel

from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset


class _Reported(BaseModel):
    findings: list[str] = []


def _specialist(instruction: str = "Look at the logs.") -> Specialist:
    return Specialist(
        name="logs_specialist",
        signal=Signal.LOGS,
        instruction=instruction,
        output_schema=_Reported,
        toolsets=(Toolset(provider="datadog", name="core", tools=("search_logs",)),),
    )


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
            toolsets=(
                Toolset(provider="datadog", name="core", tools=("search_logs",)),
            ),
        )


def test_a_toolset_that_permits_no_tool_reaches_nothing_and_is_rejected() -> None:
    with pytest.raises(ValueError, match="tool"):
        Toolset(provider="datadog", name="core", tools=())


def test_a_toolset_names_the_provider_that_serves_it() -> None:
    toolset = Toolset(provider="datadog", name="core", tools=("search_logs",))

    assert toolset.provider == "datadog"


def test_a_toolset_without_a_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="provider"):
        Toolset(provider="   ", name="core", tools=("search_logs",))


def test_one_specialist_may_declare_toolsets_on_different_providers() -> None:
    """Two providers, one declaration: the case the old shape could not express."""
    specialist = Specialist(
        name="apm_specialist",
        signal=Signal.APM,
        instruction="Look at the golden signals, and at what deployed.",
        output_schema=_Reported,
        toolsets=(
            Toolset(provider="datadog", name="metrics", tools=("query_metrics",)),
            Toolset(provider="deploy_history", name="releases", tools=("list_tags",)),
        ),
    )

    assert {toolset.provider for toolset in specialist.toolsets} == {
        "datadog",
        "deploy_history",
    }
