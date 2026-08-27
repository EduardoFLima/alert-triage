from datetime import UTC, datetime
from typing import Any

from alert_triage.investigation.adapters.adk.crew import CREW
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.datadog.specialists.logs import (
    LOGS_INSTRUCTION,
    LOGS_SPECIALIST,
    LogsFinding,
    ReportedFindings,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal
from alert_triage.investigation.domain.evidence import findings_from

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def test_the_instruction_asks_for_errors_and_warnings() -> None:
    assert "error" in LOGS_INSTRUCTION.lower()
    assert "warning" in LOGS_INSTRUCTION.lower()


def test_the_instruction_names_the_tools_the_declaration_permits() -> None:
    for tool in LOGS_SPECIALIST.toolsets[0].tools:
        assert tool in LOGS_INSTRUCTION


def test_the_instruction_teaches_the_platforms_query_dialect() -> None:
    """A query dialect does not translate, so the specialist is taught this one."""
    assert "service:checkout" in LOGS_INSTRUCTION
    assert "status:error" in LOGS_INSTRUCTION


def test_the_instruction_asks_for_an_item_citation_for_a_pattern() -> None:
    assert "call-N/item-M" in LOGS_INSTRUCTION


def test_the_instruction_asks_for_a_call_citation_for_an_aggregate() -> None:
    assert "call-N" in LOGS_INSTRUCTION
    assert "aggregate" in LOGS_INSTRUCTION.lower()


def test_the_instruction_says_what_to_do_with_a_window_of_no_width() -> None:
    """A one-alert incident's window starts and ends at the same instant.

    Passed on as given, that is a range the platform reads as empty and answers
    with nothing — a quiet service, indistinguishable from a real one.
    """
    lowered = LOGS_INSTRUCTION.lower()

    assert "single instant" in lowered
    assert "empty range" in lowered


def test_the_instruction_forbids_concluding_from_a_failed_retrieval() -> None:
    """The gate again, in the model's own terms: a failure is not a quiet service."""
    lowered = LOGS_INSTRUCTION.lower()

    assert "failed" in lowered
    assert "quiet" in lowered


def test_the_instruction_bounds_the_examples_it_asks_for() -> None:
    assert str(MAX_EXAMPLES_PER_FINDING) in LOGS_INSTRUCTION


def test_the_instruction_forbids_naming_a_root_cause() -> None:
    """This slice observes; concluding is the Diagnostician's job."""
    assert "root cause" in LOGS_INSTRUCTION.lower()


def test_the_declaration_reports_under_the_logs_signal() -> None:
    assert LOGS_SPECIALIST.signal is Signal.LOGS


def test_the_declaration_names_its_toolset_and_its_log_tools() -> None:
    """Spelled out rather than read back off the constants they name.

    A tool name is a fact about Datadog's server, not a choice this project
    makes, so a test comparing the declaration against its own constants would
    agree with any rename and notice none. Only the live check can say a name
    is real; this is what makes changing one deliberate.
    """
    (toolset,) = LOGS_SPECIALIST.toolsets

    assert toolset.name == "core"
    assert toolset.tools == ("search_datadog_logs", "analyze_datadog_logs")


def test_the_declaration_reaches_no_tool_outside_it() -> None:
    permitted = {tool for toolset in LOGS_SPECIALIST.toolsets for tool in toolset.tools}

    assert all("log" in tool for tool in permitted)


def test_the_declaration_takes_the_deployments_model_unless_configured() -> None:
    assert LOGS_SPECIALIST.model is None


def test_the_crew_contains_the_logs_specialist() -> None:
    assert LOGS_SPECIALIST in CREW


def test_the_crew_names_each_specialist_once() -> None:
    names = [specialist.name for specialist in CREW]

    assert len(names) == len(set(names))


def test_the_schema_offers_the_model_no_place_to_write_evidence() -> None:
    """It may cite what it was shown; it may not compose it."""
    assert set(LogsFinding.model_fields) == {"observation", "occurrences", "cites"}


def test_the_schema_carries_a_list_of_findings() -> None:
    assert set(ReportedFindings.model_fields) == {"findings"}


def _reported(cites: list[str]) -> dict[str, Any]:
    return {"observation": "errors recur", "occurrences": 3, "cites": cites}


def _retrieved() -> Retrieved:
    retrieved = Retrieved()
    retrieved.retain_evidence(
        {"logs": [{"message": "OOMKilled"}, {"message": "restarting"}]}
    )
    retrieved.retain_evidence({"buckets": [{"by": "status", "count": 91}]})
    return retrieved


def test_a_finding_citing_items_is_built() -> None:
    retrieved = _retrieved()

    (finding,) = findings_from(
        [_reported(["call-1/item-1", "call-1/item-2"])],
        retrieved,
        LOGS_SPECIALIST.signal,
    ).findings

    assert [item.id for item in finding.examples] == ["call-1/item-1", "call-1/item-2"]


def test_a_finding_citing_a_call_is_built() -> None:
    retrieved = _retrieved()

    (finding,) = findings_from(
        [_reported(["call-2"])], retrieved, LOGS_SPECIALIST.signal
    ).findings

    assert [item.id for item in finding.examples] == ["call-2"]


def test_a_finding_citing_both_grains_is_built() -> None:
    retrieved = _retrieved()

    (finding,) = findings_from(
        [_reported(["call-1/item-1", "call-2"])], retrieved, LOGS_SPECIALIST.signal
    ).findings

    assert [item.id for item in finding.examples] == ["call-1/item-1", "call-2"]
