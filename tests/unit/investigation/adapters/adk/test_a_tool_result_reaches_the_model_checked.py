from typing import Any

from alert_triage.investigation.adapters.adk.evidence import (
    Retrieved,
    keep_evidence_callback,
)
from alert_triage.investigation.contract import Section, Signal
from alert_triage.investigation.domain.evidence import RETRIEVAL_FAILED, findings_from
from alert_triage.shared.window import Window


class _Tool:
    def __init__(self, name: str = "search_datadog_logs") -> None:
        self.name = name


def _result(*messages: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": "{}"}],
        "structuredContent": {"logs": [{"message": message} for message in messages]},
        "isError": False,
    }


PERMITTED = frozenset({"search_datadog_logs", "aggregate_datadog_logs"})


def _after(retrieved: Retrieved, response: Any, tool: _Tool | None = None) -> Any:
    return keep_evidence_callback(retrieved, PERMITTED, "logs_specialist")(
        tool=tool or _Tool(),
        args={"query": "service:checkout status:error"},
        tool_context=None,
        tool_response=response,
    )


def test_a_successful_result_is_retained_and_replaced_with_its_citable_form() -> None:
    retrieved = Retrieved()

    offered = _after(retrieved, _result("OOMKilled"))

    assert offered["call"] == "call-1"
    assert [item["id"] for item in offered["items"]] == ["call-1/item-1"]


def test_the_model_is_never_handed_the_result_the_platform_returned() -> None:
    retrieved = Retrieved()
    result = _result("OOMKilled")

    offered = _after(retrieved, result)

    assert offered != result
    assert "structuredContent" not in offered
    assert "isError" not in offered


def test_what_was_retained_is_what_resolves() -> None:
    retrieved = Retrieved()

    offered = _after(retrieved, _result("OOMKilled", "restarting"))

    for item in offered["items"]:
        assert retrieved.resolve(item["id"]) is not None


def test_a_result_carrying_is_error_is_refused_and_recorded() -> None:
    retrieved = Retrieved()

    offered = _after(
        retrieved,
        {"content": [{"type": "text", "text": "query syntax error"}], "isError": True},
    )

    assert offered["retrieval_failed"] is True
    assert RETRIEVAL_FAILED in str(offered)
    assert len(retrieved.failures) == 1
    assert "query syntax error" in retrieved.failures[0]


def test_a_refused_retrieval_is_never_citable() -> None:
    retrieved = Retrieved()

    _after(retrieved, {"content": [], "isError": True})

    assert retrieved.resolve("call-1") is None
    assert (
        findings_from(
            [{"observation": "quiet", "occurrences": 1, "cites": ["call-1"]}],
            retrieved,
            Signal.LOGS,
        ).findings
        == ()
    )


def test_a_refusal_cannot_be_read_as_a_search_that_found_nothing() -> None:
    retrieved = Retrieved()

    offered = _after(retrieved, {"isError": True, "content": []})

    assert "failed" in str(offered).lower()
    assert offered.get("items") is None


def test_an_error_key_takes_the_same_path_as_a_server_side_error() -> None:
    retrieved = Retrieved()

    offered = _after(retrieved, {"error": "MCP tool execution failed: 403"})

    assert offered["retrieval_failed"] is True
    assert "403" in retrieved.failures[0]
    assert retrieved.resolve("call-1") is None


def test_a_result_that_found_nothing_is_not_a_failure() -> None:
    retrieved = Retrieved()

    offered = _after(retrieved, _result())

    assert offered["call"] == "call-1"
    assert offered["items"] == []
    assert retrieved.failures == ()


def test_failures_and_evidence_accumulate_together_across_an_investigation() -> None:
    retrieved = Retrieved()

    _after(retrieved, _result("first"))
    _after(retrieved, {"isError": True, "content": []})
    _after(retrieved, _result("second"))
    _after(retrieved, {"error": "MCP tool execution failed: 500"})
    _after(retrieved, _result("third"))

    assert len(retrieved.failures) == 2
    assert retrieved.retrievals == 3
    assert [retrieved.resolve(f"call-{n}/item-1").summary for n in (1, 2, 3)] == [  # type: ignore[union-attr]
        "first",
        "second",
        "third",
    ]


def test_the_failure_names_the_tool_that_could_not_be_reached() -> None:
    retrieved = Retrieved()

    _after(retrieved, {"error": "403"}, _Tool("aggregate_datadog_logs"))

    assert "aggregate_datadog_logs" in retrieved.failures[0]


def test_a_tool_the_specialist_never_declared_passes_through_untouched() -> None:
    retrieved = Retrieved()

    offered = _after(retrieved, {"result": "response set"}, _Tool("set_model_response"))

    assert offered is None
    assert retrieved.retrievals == 0
    assert retrieved.failures == ()


def test_a_framework_tool_that_fails_is_not_a_failed_retrieval() -> None:
    retrieved = Retrieved()

    _after(retrieved, {"error": "transfer refused"}, _Tool("transfer_to_agent"))

    assert retrieved.failures == ()


class _Args:
    def __init__(self) -> None:
        self.seen: list[tuple[Any, Any]] = []

    def to_retrieval(
        self, tool: str, args: Any, service: str = "", env: str | None = None
    ) -> str | None:
        self.seen.append((tool, args))
        return "https://platform/search"

    def to_item(
        self,
        tool: str,
        payload: Any,
        within: str | None,
        service: str = "",
        env: str | None = None,
    ) -> str | None:
        return within

    def to_service(
        self,
        service: str,
        window: Window,
        section: Section | None,
        env: str | None = None,
    ) -> str | None:
        return None


def test_what_keeps_a_result_is_told_the_tools_name_and_arguments() -> None:
    links = _Args()
    retrieved = Retrieved(link=links)

    _after(retrieved, _result("OOMKilled"))

    assert [tool for tool, _ in links.seen] == ["search_datadog_logs"]
    assert [args for _, args in links.seen] == [
        {"query": "service:checkout status:error"}
    ]


def test_a_failed_retrieval_is_still_refused_rather_than_addressed() -> None:
    links = _Args()
    retrieved = Retrieved(link=links)

    offered = _after(retrieved, {"isError": True, "content": []})

    assert offered["retrieval_failed"] is True
    assert links.seen == []
    assert retrieved.resolve("call-1") is None


def test_the_model_is_shown_no_address_it_could_copy_into_a_finding() -> None:
    retrieved = Retrieved(link=_Args())

    offered = _after(retrieved, _result("OOMKilled"))

    (item,) = offered["items"]
    assert set(item) == {"id", "instant", "summary", "data"}
    assert "https://" not in str(offered)


def test_an_aggregate_is_offered_without_an_address_either() -> None:
    retrieved = Retrieved(link=_Args())

    offered = _after(retrieved, {"content": [{"type": "text", "text": '{"count": 4}'}]})

    assert set(offered) == {"call", "items", "summary", "data", "cite_as"}
    assert "https://" not in str(offered)
