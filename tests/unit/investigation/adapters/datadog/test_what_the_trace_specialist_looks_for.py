"""The trace specialist's declaration: what it may reach and what it is asked.

Its own risk is not the tool names but the model's fluency: a trace waterfall
is exactly the kind of thing a language model can describe convincingly having
retrieved nothing. So the instruction is asserted to demand a retrieved
request, and the schema to offer nowhere to write one.
"""

import re

from alert_triage.investigation.adapters.datadog.specialists.trace import (
    TRACE_INSTRUCTION,
    TRACE_SPECIALIST,
    ReportedFindings,
    TraceFinding,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal

QUOTED_IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")


def _permitted() -> set[str]:
    return {tool for toolset in TRACE_SPECIALIST.toolsets for tool in toolset.tools}


def _tools_named_in(instruction: str) -> set[str]:
    return {
        quoted
        for quoted in re.findall(r"`([^`]+)`", instruction)
        if QUOTED_IDENTIFIER.fullmatch(quoted)
    }


def test_the_declaration_reports_under_the_trace_signal() -> None:
    assert TRACE_SPECIALIST.signal is Signal.TRACE


def test_the_declaration_reaches_the_platforms_core_toolset_alone() -> None:
    (toolset,) = TRACE_SPECIALIST.toolsets

    assert toolset.name == "core"


def test_the_declaration_permits_the_two_tools_it_needs_and_no_others() -> None:
    assert _permitted() == {"search_datadog_spans", "get_datadog_trace"}


def test_the_declaration_takes_the_deployments_model_unless_configured() -> None:
    assert TRACE_SPECIALIST.model is None


def test_the_instruction_asks_for_the_spans_before_the_trace() -> None:
    """A trace is fetched by identifier, and the search is where one comes from."""
    lowered = TRACE_INSTRUCTION.lower()

    assert lowered.index("search_datadog_spans") < lowered.index("get_datadog_trace")
    assert "before" in lowered


def test_the_instruction_asks_where_the_time_went_or_where_the_request_broke() -> None:
    lowered = TRACE_INSTRUCTION.lower()

    assert "time" in lowered
    assert "broke" in lowered or "failed" in lowered


def test_the_instruction_forbids_describing_a_typical_request() -> None:
    """The one thing a fluent model will do unprompted, forbidden in as many words."""
    lowered = TRACE_INSTRUCTION.lower()

    assert "typical" in lowered
    assert "retrieved" in lowered


def test_the_instruction_asks_for_both_citation_grains() -> None:
    assert "call-N/item-M" in TRACE_INSTRUCTION
    assert "call-N" in TRACE_INSTRUCTION


def test_the_instruction_bounds_the_examples_it_asks_for() -> None:
    assert str(MAX_EXAMPLES_PER_FINDING) in TRACE_INSTRUCTION


def test_the_instruction_forbids_concluding_from_a_failed_retrieval() -> None:
    """Asserted on the flowed text: the wrapping of a paragraph is not a rule."""
    flowed = " ".join(TRACE_INSTRUCTION.lower().split())

    assert "failed" in flowed
    assert "the retrieval did not run" in flowed


def test_the_instruction_forbids_naming_a_root_cause() -> None:
    assert "root cause" in TRACE_INSTRUCTION.lower()


def test_every_tool_the_declaration_permits_is_named_in_the_instruction() -> None:
    for tool in _permitted():
        assert tool in TRACE_INSTRUCTION


def test_every_tool_the_instruction_names_is_one_the_declaration_permits() -> None:
    assert _tools_named_in(TRACE_INSTRUCTION) == _permitted()


def test_the_schema_offers_the_model_no_place_to_write_evidence() -> None:
    assert set(TraceFinding.model_fields) == {"observation", "occurrences", "cites"}


def test_the_schema_carries_a_list_of_findings() -> None:
    assert set(ReportedFindings.model_fields) == {"findings"}
