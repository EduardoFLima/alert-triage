"""The infrastructure specialist's declaration: what it may reach and what it is asked.

The specialist whose signal a deployment may genuinely not have. A service on
virtual machines has no container workload, and the platform says so by
answering that there are none. The instruction has to tell the model that this
is an answer, because a model told to find the workload will otherwise keep
asking, or report the absence as something wrong.
"""

from alert_triage.investigation.adapters.datadog.specialists.infrastructure import (
    INFRASTRUCTURE_INSTRUCTION,
    INFRASTRUCTURE_SPECIALIST,
    InfrastructureFinding,
    ReportedFindings,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal


def _permitted() -> set[str]:
    return {
        tool for toolset in INFRASTRUCTURE_SPECIALIST.toolsets for tool in toolset.tools
    }


def _flowed() -> str:
    return " ".join(INFRASTRUCTURE_INSTRUCTION.lower().split())


def test_the_declaration_reports_under_the_infrastructure_signal() -> None:
    assert INFRASTRUCTURE_SPECIALIST.signal is Signal.INFRASTRUCTURE


def test_the_declaration_reaches_the_core_and_kubernetes_toolsets() -> None:
    assert {toolset.name for toolset in INFRASTRUCTURE_SPECIALIST.toolsets} == {
        "core",
        "kubernetes",
    }


def test_the_declaration_permits_the_tools_it_needs_and_no_others() -> None:
    assert _permitted() == {
        "get_datadog_metric",
        "search_datadog_metrics",
        "get_datadog_metric_context",
        "search_datadog_hosts",
        "search_datadog_k8s_resources",
        "describe_datadog_k8s_resource",
        "list_datadog_skills",
        "load_datadog_skill",
    }


def test_the_declaration_can_list_the_metrics_a_host_or_service_reports() -> None:
    """Metric context answers about a metric you name; it enumerates none."""
    assert "search_datadog_metrics" in _permitted()


def test_the_declaration_can_discover_a_metric_before_querying_it() -> None:
    """A guessed metric name comes back empty, which now reads as a quiet signal."""
    assert "get_datadog_metric_context" in _permitted()


def test_the_instruction_asks_the_listing_tool_which_metrics_are_reported() -> None:
    """The failure this prevents: metric context asked to enumerate a service.

    Asked for everything a service reports it has no such argument, so a model
    told to ask it that sends `*` as the metric name and the platform refuses
    the retrieval.
    """
    assert "ask `search_datadog_metrics` which metrics" in _flowed()


def test_the_instruction_says_to_discover_a_metric_before_querying_it() -> None:
    assert "search_datadog_metrics" in INFRASTRUCTURE_INSTRUCTION
    assert "guess" in _flowed()


def test_the_declaration_takes_the_deployments_model_unless_configured() -> None:
    assert INFRASTRUCTURE_SPECIALIST.model is None


def test_the_instruction_asks_for_every_resource_that_saturates() -> None:
    lowered = INFRASTRUCTURE_INSTRUCTION.lower()

    for resource in ("cpu", "memory", "disk", "network"):
        assert resource in lowered


def test_the_instruction_asks_for_the_workload_state_and_its_restarts() -> None:
    lowered = INFRASTRUCTURE_INSTRUCTION.lower()

    assert "workload" in lowered
    assert "restart" in lowered


def test_the_instruction_says_an_absent_signal_is_an_answer_not_a_failure() -> None:
    """A service that is not on containers is not a retrieval that broke."""
    flowed = _flowed()

    assert "does not have" in flowed
    assert "not a failure" in flowed


def test_the_instruction_asks_for_both_citation_grains() -> None:
    assert "call-N/item-M" in INFRASTRUCTURE_INSTRUCTION
    assert "call-N" in INFRASTRUCTURE_INSTRUCTION


def test_the_instruction_bounds_the_examples_it_asks_for() -> None:
    assert str(MAX_EXAMPLES_PER_FINDING) in INFRASTRUCTURE_INSTRUCTION


def test_the_instruction_forbids_concluding_from_a_failed_retrieval() -> None:
    flowed = _flowed()

    assert "failed" in flowed
    assert "the retrieval did not run" in flowed


def test_a_failed_retrieval_and_an_absent_signal_are_told_apart() -> None:
    """The two the model must never conflate, distinguished where it reads them."""
    flowed = _flowed()

    assert flowed.index("does not have") != flowed.index("the retrieval did not run")


def test_the_instruction_forbids_naming_a_root_cause() -> None:
    assert "root cause" in INFRASTRUCTURE_INSTRUCTION.lower()


def test_the_schema_offers_the_model_no_place_to_write_evidence() -> None:
    assert set(InfrastructureFinding.model_fields) == {
        "observation",
        "occurrences",
        "cites",
    }


def test_the_schema_carries_a_list_of_findings() -> None:
    assert set(ReportedFindings.model_fields) == {"findings"}
