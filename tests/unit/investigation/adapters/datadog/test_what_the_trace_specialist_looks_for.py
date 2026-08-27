"""The trace specialist's declaration: what it may reach and what it is asked.

Its own risk is not the tool names but the model's fluency: a trace waterfall
is exactly the kind of thing a language model can describe convincingly having
retrieved nothing. So the instruction is asserted to demand a retrieved
request, and the schema to offer nowhere to write one.
"""

from alert_triage.investigation.adapters.datadog.specialists.trace import (
    TRACE_INSTRUCTION,
    TRACE_SPECIALIST,
    ReportedFindings,
    TraceFinding,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal


def _permitted() -> set[str]:
    return {tool for toolset in TRACE_SPECIALIST.toolsets for tool in toolset.tools}


def test_the_declaration_reports_under_the_trace_signal() -> None:
    assert TRACE_SPECIALIST.signal is Signal.TRACE


def test_the_declaration_reaches_the_platforms_core_and_apm_toolsets() -> None:
    assert {toolset.name for toolset in TRACE_SPECIALIST.toolsets} == {"core", "apm"}


def test_the_declaration_permits_the_tools_it_needs_and_no_others() -> None:
    assert _permitted() == {
        "search_datadog_spans",
        "get_datadog_trace",
        "apm_query_trace",
    }


def test_the_declaration_can_rank_within_a_trace_rather_than_reading_it_whole() -> None:
    """Which operation dominated is a ranking question, not a reading exercise."""
    assert "apm_query_trace" in _permitted()


def test_the_instruction_asks_it_to_rank_within_a_fetched_trace() -> None:
    assert "apm_query_trace" in TRACE_INSTRUCTION


def test_the_declaration_takes_the_deployments_model_unless_configured() -> None:
    assert TRACE_SPECIALIST.model is None


def test_the_instruction_asks_for_the_spans_before_the_trace() -> None:
    """A trace is fetched by identifier, and the search is where one comes from."""
    lowered = TRACE_INSTRUCTION.lower()

    assert lowered.index("search_datadog_spans") < lowered.index("get_datadog_trace")
    assert lowered.index("get_datadog_trace") < lowered.index("apm_query_trace")
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


def test_the_schema_offers_the_model_no_place_to_write_evidence() -> None:
    assert set(TraceFinding.model_fields) == {"observation", "occurrences", "cites"}


def test_the_schema_carries_a_list_of_findings() -> None:
    assert set(ReportedFindings.model_fields) == {"findings"}
