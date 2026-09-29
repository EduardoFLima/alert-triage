from datetime import UTC, datetime
from typing import Any

from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.adapters.crew.specialists.logs import (
    LOGS_INSTRUCTION,
    LOGS_SPECIALIST,
)
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.evidence import findings_from

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def test_the_instruction_asks_for_errors_and_warnings() -> None:
    assert "error" in LOGS_INSTRUCTION.lower()
    assert "warning" in LOGS_INSTRUCTION.lower()


def test_the_instruction_teaches_the_platforms_query_dialect() -> None:
    assert "service:checkout" in LOGS_INSTRUCTION
    assert "status:error" in LOGS_INSTRUCTION


def test_the_instruction_asks_for_an_item_citation_for_a_pattern() -> None:
    assert "call-N/item-M" in LOGS_INSTRUCTION


def test_the_instruction_asks_for_a_call_citation_for_an_aggregate() -> None:
    assert "call-N" in LOGS_INSTRUCTION
    assert "aggregate" in LOGS_INSTRUCTION.lower()


def test_the_instruction_says_what_to_do_with_a_window_of_no_width() -> None:
    lowered = LOGS_INSTRUCTION.lower()

    assert "single instant" in lowered
    assert "empty range" in lowered


def test_the_instruction_says_where_a_widened_window_goes() -> None:
    lowered = LOGS_INSTRUCTION.lower()

    assert "`from`" in lowered
    assert "never in sql" in lowered


def test_the_instruction_offers_the_clustering_the_task_is_asking_for() -> None:
    assert "use_log_patterns" in LOGS_INSTRUCTION


def test_the_instruction_forbids_concluding_from_a_failed_retrieval() -> None:
    lowered = LOGS_INSTRUCTION.lower()

    assert "failed" in lowered
    assert "quiet" in lowered


def test_the_declaration_reports_under_the_logs_signal() -> None:
    assert LOGS_SPECIALIST.signal is Signal.LOGS


def test_the_declaration_names_its_toolset_and_its_log_tools() -> None:
    (toolset,) = LOGS_SPECIALIST.toolsets

    assert toolset.name == "core"
    assert toolset.tools == (
        "search_datadog_logs",
        "analyze_datadog_logs",
    )


def test_the_declaration_reaches_no_tool_outside_it() -> None:
    permitted = {tool for toolset in LOGS_SPECIALIST.toolsets for tool in toolset.tools}

    assert all("log" in tool for tool in permitted)


def _reported(cites: list[str]) -> dict[str, Any]:
    return {"observation": "errors recur", "occurrences": 3, "cites": cites}


def _retrieved() -> Retrieved:
    retrieved = Retrieved()
    retrieved.retain_evidence(
        "search_logs", {"logs": [{"message": "OOMKilled"}, {"message": "restarting"}]}
    )
    retrieved.retain_evidence(
        "search_logs", {"buckets": [{"by": "status", "count": 91}]}
    )
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
