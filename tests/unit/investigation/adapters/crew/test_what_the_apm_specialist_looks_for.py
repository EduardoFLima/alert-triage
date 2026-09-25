"""The APM specialist's declaration: what it may reach and what it is asked.

Everything here is read off module constants. What a declaration permits and
what its instruction names have to agree, and the cheapest way for them to
disagree is a copy-paste, so both directions are asserted.
"""

from alert_triage.investigation.adapters.crew.specialists.apm import (
    APM_INSTRUCTION,
    APM_SPECIALIST,
    ApmFinding,
    ReportedFindings,
    apm_specialist,
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


PREVIEW_TOOLS = {
    "apm_latency_bottleneck_summary",
    "apm_search_watchdog_stories",
    "get_change_stories",
    "semantic_search_change_stories",
}


def test_without_preview_it_reaches_the_core_toolset_alone() -> None:
    """An account without Preview must not be told it has a tool it cannot call."""
    without = apm_specialist(preview=False)

    assert {toolset.name for toolset in without.toolsets} == {"core"}


def test_without_preview_it_permits_the_tools_it_needs_and_no_others() -> None:
    assert _permitted(apm_specialist(preview=False)) == {
        "get_datadog_metric",
        "get_datadog_metric_context",
        "search_datadog_metrics",
        "search_datadog_entities",
        "search_datadog_events",
    }


RETIRED_TOOL = "search_datadog_service_dependencies"
"""Deprecated by the platform in favour of its catalogue search."""


def test_no_declaration_permits_or_names_the_retired_dependency_tool() -> None:
    """A tool the platform stops serving comes back as a refused retrieval."""
    for preview in (False, True):
        declared = apm_specialist(preview=preview)

        assert RETIRED_TOOL not in _permitted(declared)
        assert RETIRED_TOOL not in declared.instruction


def test_both_declarations_reach_the_catalogue() -> None:
    for preview in (False, True):
        declared = apm_specialist(preview=preview)

        assert "search_datadog_entities" in _permitted(declared)
        assert "search_datadog_entities" in declared.instruction


def test_the_instruction_says_what_to_ask_the_catalogue_for() -> None:
    """A search handed over as a lookup is searched for the service and nothing else.

    The retired tool took a service and answered with its neighbours; the
    catalogue has to be asked, so the line describing it names the ask.
    """
    for preview in (False, True):
        instruction = apm_specialist(preview=preview).instruction
        described = instruction[instruction.index("`search_datadog_entities`") :]
        bullet_and_what_follows = "\n\n".join(described.split("\n\n")[:2])
        line = " ".join(bullet_and_what_follows.split())

        assert "ask it for" in line.lower()
        assert "upstream and downstream" in line.lower()


def test_without_preview_no_preview_tool_is_permitted_or_named() -> None:
    """The gate: a tool the server would refuse comes back as a failed retrieval."""
    without = apm_specialist(preview=False)

    assert not PREVIEW_TOOLS & _permitted(without)
    assert not any(tool in without.instruction for tool in PREVIEW_TOOLS)


def test_without_preview_deploy_correlation_survives_through_events() -> None:
    """The one Preview capability core can still answer, coarsely."""
    without = apm_specialist(preview=False)

    assert "search_datadog_events" in _permitted(without)
    assert "search_datadog_events" in without.instruction


def test_with_preview_it_reaches_both_the_core_and_apm_toolsets() -> None:
    with_preview = apm_specialist(preview=True)

    assert {toolset.name for toolset in with_preview.toolsets} == {"core", "apm"}


def test_with_preview_it_permits_the_tools_it_needs_and_no_others() -> None:
    assert (
        _permitted(apm_specialist(preview=True))
        == {
            "get_datadog_metric",
            "get_datadog_metric_context",
            "search_datadog_metrics",
            "search_datadog_entities",
        }
        | PREVIEW_TOOLS
    )


def test_with_preview_change_stories_supersede_raw_events() -> None:
    """Two tools answering one question is two ways to spend a call on it."""
    assert "search_datadog_events" not in _permitted(apm_specialist(preview=True))


def test_the_declaration_can_list_the_metrics_a_service_reports() -> None:
    """Metric context answers about a metric you name; it enumerates none."""
    assert "search_datadog_metrics" in _permitted(APM_SPECIALIST)


def test_the_declaration_can_discover_a_metric_before_querying_it() -> None:
    """A guessed metric name comes back empty, which now reads as a quiet signal."""
    assert "get_datadog_metric_context" in _permitted(APM_SPECIALIST)


def test_the_instruction_asks_the_listing_tool_which_metrics_exist() -> None:
    """The failure this prevents: metric context asked to enumerate a service.

    Asked for a whole service's metrics it has no such argument, so a model
    told to ask it that sends `*` as the metric name and the platform refuses
    the retrieval.
    """
    flowed = " ".join(APM_INSTRUCTION.lower().split())

    assert "ask `search_datadog_metrics` which metrics" in flowed


def test_the_instruction_says_to_discover_a_metric_before_querying_it() -> None:
    ordering = APM_INSTRUCTION.index("search_datadog_metrics")

    assert ordering < APM_INSTRUCTION.index("Rules you must follow")
    assert "guess" in APM_INSTRUCTION.lower()


def test_with_preview_the_instruction_asks_what_the_platform_already_noticed() -> None:
    assert "apm_search_watchdog_stories" in apm_specialist(preview=True).instruction


def test_with_preview_the_instruction_asks_where_the_latency_went() -> None:
    assert "apm_latency_bottleneck_summary" in apm_specialist(preview=True).instruction


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


def test_the_aggregate_example_does_not_assume_the_catalogues_grain() -> None:
    """Whether the catalogue answers in discrete entities is a live question."""
    for preview in (False, True):
        flowed = " ".join(apm_specialist(preview=preview).instruction.split())

        assert "dependency map" not in flowed


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
