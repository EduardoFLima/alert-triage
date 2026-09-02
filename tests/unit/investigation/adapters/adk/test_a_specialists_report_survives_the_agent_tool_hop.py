"""What a specialist reports reaches the findings, not the manager's retelling.

The manager reaches each specialist as a tool, so a specialist's structured
report arrives as a tool result. It is checked and collected there — before the
manager reads it — because a finding that went through a model on its way to the
report is a finding nobody checked.
"""

from typing import Any

from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.consultation import (
    Consulted,
    collect_findings_callback,
)
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset


class _Reported(BaseModel):
    findings: list[dict[str, Any]] = []


def _specialist(
    name: str = "logs_specialist", signal: Signal = Signal.LOGS
) -> Specialist:
    return Specialist(
        name=name,
        signal=signal,
        instruction="Look at the logs.",
        output_schema=_Reported,
        toolsets=(Toolset(name="core", tools=("search_datadog_logs",)),),
    )


class _Tool:
    """What ADK hands a callback in place of the tool it just ran."""

    def __init__(self, name: str) -> None:
        self.name = name


def _consulted(*crew: Specialist) -> tuple[Consulted, Retrieved]:
    retrieved = Retrieved()
    retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
    return Consulted(offered=crew or (_specialist(),), retrieved=retrieved), retrieved


def _report(*cites: str) -> dict[str, Any]:
    return {
        "findings": [
            {"observation": "OOMKilled recurs", "occurrences": 3, "cites": list(cites)}
        ]
    }


def test_what_a_specialist_reported_is_checked_and_collected() -> None:
    consulted, _ = _consulted()
    collect = collect_findings_callback(consulted)

    collect(
        tool=_Tool("logs_specialist"),
        args={"request": "look at the logs"},
        tool_context=None,
        tool_response=_report("call-1/item-1"),
    )

    (finding,) = consulted.findings
    assert finding.signal is Signal.LOGS
    assert finding.examples[0].summary == "OOMKilled"


def test_the_manager_reads_the_specialists_report_unchanged() -> None:
    """The callback collects; it does not stand between the manager and its answer."""
    consulted, _ = _consulted()
    collect = collect_findings_callback(consulted)
    reported = _report("call-1/item-1")

    assert (
        collect(
            tool=_Tool("logs_specialist"),
            args={},
            tool_context=None,
            tool_response=reported,
        )
        is None
    )


def test_a_result_from_something_that_is_not_a_specialist_is_left_alone() -> None:
    consulted, _ = _consulted()
    collect = collect_findings_callback(consulted)

    collect(
        tool=_Tool("some_framework_tool"),
        args={},
        tool_context=None,
        tool_response=_report("call-1/item-1"),
    )

    assert consulted.findings == ()
    assert consulted.order == ()


def test_a_report_the_callback_cannot_read_contributes_nothing_and_does_not_raise() -> (
    None
):
    """A specialist that said nothing legible is not a crashed investigation."""
    consulted, _ = _consulted()
    collect = collect_findings_callback(consulted)

    collect(
        tool=_Tool("logs_specialist"),
        args={},
        tool_context=None,
        tool_response="the logs looked fine to me",
    )

    assert consulted.findings == ()


def test_an_illegible_report_still_counts_as_a_specialist_consulted() -> None:
    """What was asked is a different fact from what came back legibly."""
    consulted, _ = _consulted()
    collect = collect_findings_callback(consulted)

    collect(
        tool=_Tool("logs_specialist"),
        args={},
        tool_context=None,
        tool_response=None,
    )

    assert consulted.order == ("logs_specialist",)
    assert consulted.signals == (Signal.LOGS,)


def test_a_report_arriving_as_json_in_a_result_field_is_read() -> None:
    """The framework may hand a sub-agent's answer over as text rather than a record."""
    import json

    consulted, _ = _consulted()
    collect = collect_findings_callback(consulted)

    collect(
        tool=_Tool("logs_specialist"),
        args={},
        tool_context=None,
        tool_response={"result": json.dumps(_report("call-1/item-1"))},
    )

    (finding,) = consulted.findings
    assert finding.observation == "OOMKilled recurs"
