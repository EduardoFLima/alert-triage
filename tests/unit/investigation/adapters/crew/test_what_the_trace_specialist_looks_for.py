from alert_triage.investigation.adapters.crew.specialists.trace import (
    TRACE_INSTRUCTION,
    TRACE_SPECIALIST,
    trace_specialist,
)
from alert_triage.investigation.adapters.datadog.dialect import AN_EMPTY_ANSWER
from alert_triage.investigation.contract import Signal


def test_the_declaration_reports_under_the_trace_signal() -> None:
    assert TRACE_SPECIALIST.signal is Signal.TRACE


def _tools(specialist: object) -> set[str]:
    return {
        tool
        for toolset in specialist.toolsets  # type: ignore[attr-defined]
        for tool in toolset.tools
    }


def test_without_preview_it_reaches_the_core_toolset_alone() -> None:
    without = trace_specialist(preview=False)

    assert {toolset.name for toolset in without.toolsets} == {"core"}
    assert _tools(without) == {
        "search_datadog_spans",
        "get_datadog_trace",
    }


def test_without_preview_ranking_is_neither_permitted_nor_named() -> None:
    without = trace_specialist(preview=False)

    assert "apm_query_trace" not in _tools(without)
    assert "apm_query_trace" not in without.instruction


def test_without_preview_it_is_still_told_to_account_for_where_time_went() -> None:
    without = trace_specialist(preview=False)

    assert "before you fetch" in without.instruction.lower()
    assert "where the time went" in without.instruction.lower()


def test_with_preview_it_reaches_both_the_core_and_apm_toolsets() -> None:
    with_preview = trace_specialist(preview=True)

    assert {toolset.name for toolset in with_preview.toolsets} == {"core", "apm"}
    assert _tools(with_preview) == {
        "search_datadog_spans",
        "get_datadog_trace",
        "apm_query_trace",
        "apm_discover_span_tags",
    }


def test_without_preview_facet_discovery_is_neither_permitted_nor_named() -> None:
    without = trace_specialist(preview=False)

    assert "apm_discover_span_tags" not in _tools(without)
    assert "apm_discover_span_tags" not in without.instruction


def test_with_preview_it_can_ask_which_facets_a_service_carries() -> None:
    with_preview = trace_specialist(preview=True)

    assert "apm_discover_span_tags" in _tools(with_preview)
    assert "apm_discover_span_tags" in with_preview.instruction


def test_with_preview_it_is_told_to_rank_within_a_fetched_trace() -> None:
    assert "apm_query_trace" in trace_specialist(preview=True).instruction


def test_the_instruction_asks_for_the_spans_before_the_trace() -> None:
    lowered = TRACE_INSTRUCTION.lower()

    assert lowered.index("search_datadog_spans") < lowered.index("get_datadog_trace")
    assert "before" in lowered


def test_with_preview_the_instruction_orders_all_three_steps() -> None:
    lowered = trace_specialist(preview=True).instruction.lower()

    assert lowered.index("search_datadog_spans") < lowered.index("get_datadog_trace")
    assert lowered.index("get_datadog_trace") < lowered.index("apm_query_trace")


def test_the_instruction_asks_where_the_time_went_or_where_the_request_broke() -> None:
    lowered = TRACE_INSTRUCTION.lower()

    assert "time" in lowered
    assert "broke" in lowered or "failed" in lowered


def test_the_instruction_forbids_describing_a_typical_request() -> None:
    lowered = TRACE_INSTRUCTION.lower()

    assert "typical" in lowered
    assert "retrieved" in lowered


def test_an_empty_span_search_is_read_as_a_question_about_the_query() -> None:
    for preview in (False, True):
        instruction = trace_specialist(preview=preview).instruction
        flowed = " ".join(instruction.lower().split())

        assert AN_EMPTY_ANSWER in instruction
        assert "about your query rather than about the service" in flowed
        assert "do not guess a facet" in flowed


def test_the_instruction_asks_for_both_citation_grains() -> None:
    assert "call-N/item-M" in TRACE_INSTRUCTION
    assert "call-N" in TRACE_INSTRUCTION


def test_the_instruction_forbids_concluding_from_a_failed_retrieval() -> None:
    flowed = " ".join(TRACE_INSTRUCTION.lower().split())

    assert "failed" in flowed
    assert "the retrieval did not run" in flowed
