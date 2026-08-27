"""The APM specialist's declaration: what it may reach and what it is asked.

Everything here is read off module constants. What a declaration permits and
what its instruction names have to agree, and the cheapest way for them to
disagree is a copy-paste, so both directions are asserted.
"""

from alert_triage.investigation.adapters.datadog.specialists.apm import (
    APM_INSTRUCTION,
    APM_SPECIALIST,
    ApmFinding,
    ReportedFindings,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal


def _permitted(specialist: object) -> set[str]:
    return {
        tool
        for toolset in specialist.toolsets  # type: ignore[attr-defined]
        for tool in toolset.tools
    }


def test_the_declaration_reports_under_the_apm_signal() -> None:
    assert APM_SPECIALIST.signal is Signal.APM


def test_the_declaration_reaches_both_the_platforms_core_and_apm_toolsets() -> None:
    """The first specialist to reach more than one toolset."""
    assert {toolset.name for toolset in APM_SPECIALIST.toolsets} == {"core", "apm"}


def test_the_declaration_permits_the_tools_it_needs_and_no_others() -> None:
    assert _permitted(APM_SPECIALIST) == {
        "get_datadog_metric",
        "get_datadog_metric_context",
        "search_datadog_service_dependencies",
        "apm_latency_bottleneck_summary",
        "apm_search_watchdog_stories",
        "get_change_stories",
        "semantic_search_change_stories",
    }


def test_the_declaration_can_discover_a_metric_before_querying_it() -> None:
    """A guessed metric name comes back empty, which now reads as a quiet signal."""
    assert "get_datadog_metric_context" in _permitted(APM_SPECIALIST)


def test_the_instruction_says_to_discover_a_metric_before_querying_it() -> None:
    ordering = APM_INSTRUCTION.index("get_datadog_metric_context")

    assert ordering < APM_INSTRUCTION.index("Rules you must follow")
    assert "guess" in APM_INSTRUCTION.lower()


def test_the_instruction_asks_what_the_platform_already_noticed() -> None:
    assert "apm_search_watchdog_stories" in APM_INSTRUCTION


def test_the_declaration_takes_the_deployments_model_unless_configured() -> None:
    assert APM_SPECIALIST.model is None


def test_the_instruction_asks_for_the_golden_signals() -> None:
    lowered = APM_INSTRUCTION.lower()

    assert "latency" in lowered
    assert "error rate" in lowered
    assert "throughput" in lowered


def test_the_instruction_teaches_the_platforms_metric_query_dialect() -> None:
    """A query dialect does not translate, so the specialist is taught this one."""
    assert "avg:" in APM_INSTRUCTION
    assert "service:checkout" in APM_INSTRUCTION


def test_the_instruction_asks_for_single_hop_dependency_evidence() -> None:
    lowered = APM_INSTRUCTION.lower()

    assert "neighbour" in lowered
    assert "one hop" in lowered


def test_the_instruction_forbids_investigating_the_neighbour_in_its_own_right() -> None:
    """A neighbour is context for this service, not a second investigation."""
    lowered = APM_INSTRUCTION.lower()

    assert "do not investigate" in lowered


def test_the_instruction_asks_what_changed_close_to_the_alerts() -> None:
    lowered = APM_INSTRUCTION.lower()

    assert "change" in lowered
    assert "landed" in lowered


def test_the_instruction_forbids_naming_a_change_as_the_cause() -> None:
    """A coincidence in time is something observed, not a conclusion."""
    lowered = APM_INSTRUCTION.lower()

    assert "coincidence" in lowered or "do not name" in lowered


def test_the_instruction_asks_for_both_citation_grains() -> None:
    assert "call-N/item-M" in APM_INSTRUCTION
    assert "call-N" in APM_INSTRUCTION


def test_the_instruction_bounds_the_examples_it_asks_for() -> None:
    assert str(MAX_EXAMPLES_PER_FINDING) in APM_INSTRUCTION


def test_the_instruction_forbids_concluding_from_a_failed_retrieval() -> None:
    """A failure is not a healthy service, in either direction."""
    lowered = APM_INSTRUCTION.lower()

    assert "failed" in lowered
    assert "steady" in lowered or "healthy" in lowered


def test_the_instruction_forbids_naming_a_root_cause() -> None:
    assert "root cause" in APM_INSTRUCTION.lower()


def test_the_schema_offers_the_model_no_place_to_write_evidence() -> None:
    """It may cite what it was shown; it may not compose it."""
    assert set(ApmFinding.model_fields) == {"observation", "occurrences", "cites"}


def test_the_schema_carries_a_list_of_findings() -> None:
    assert set(ReportedFindings.model_fields) == {"findings"}
