"""The callback standing between a tool result and the model about to read it.

A result from a declared tool is kept and replaced with its citable form; one
that failed is refused in terms nothing can misread; anything the specialist
never declared passes through untouched.
"""

import logging
from typing import Any

import pytest

from alert_triage.investigation.adapters.adk.evidence import (
    Retrieved,
    log_tool_call,
    keep_evidence_callback,
)
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.evidence import RETRIEVAL_FAILED, findings_from


class _Tool:
    """A stand-in for the ADK tool the callback is told about."""

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
    return keep_evidence_callback(retrieved, PERMITTED)(
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
    """What the model reads is what it may cite, and nothing else."""
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
    """The gate: a failure the model reads as silence is the opposite finding."""
    retrieved = Retrieved()

    offered = _after(retrieved, {"isError": True, "content": []})

    assert "failed" in str(offered).lower()
    assert offered.get("items") is None


def test_an_error_key_takes_the_same_path_as_a_server_side_error() -> None:
    """This is the shape ADK converts an exception into."""
    retrieved = Retrieved()

    offered = _after(retrieved, {"error": "MCP tool execution failed: 403"})

    assert offered["retrieval_failed"] is True
    assert "403" in retrieved.failures[0]
    assert retrieved.resolve("call-1") is None


def test_a_result_that_cannot_be_read_at_all_is_a_failure_not_an_empty_answer() -> None:
    retrieved = Retrieved()

    offered = _after(retrieved, None)

    assert offered["retrieval_failed"] is True
    assert retrieved.failures


def test_a_result_that_found_nothing_is_not_a_failure() -> None:
    """A quiet service is a result; only a broken retrieval is a failure."""
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


def test_the_call_is_logged_before_it_is_made_and_nothing_else_happens(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Slice 12's seat, with a test already on it."""
    with caplog.at_level(logging.INFO):
        refused = log_tool_call()(
            tool=_Tool(), args={"query": "status:error"}, tool_context=None
        )

    assert refused is None
    assert "search_datadog_logs" in caplog.text


def test_a_tool_the_specialist_never_declared_passes_through_untouched() -> None:
    """A framework's own tool is not the platform, so its result is not evidence."""
    retrieved = Retrieved()

    offered = _after(retrieved, {"result": "response set"}, _Tool("set_model_response"))

    assert offered is None
    assert retrieved.retrievals == 0
    assert retrieved.failures == ()


def test_a_framework_tool_that_fails_is_not_a_failed_retrieval() -> None:
    """Nothing was retrieved, so nothing about the platform can be concluded."""
    retrieved = Retrieved()

    _after(retrieved, {"error": "transfer refused"}, _Tool("transfer_to_agent"))

    assert retrieved.failures == ()


class _Args:
    """Keeps what a retrieval was told the tool was called with."""

    def __init__(self) -> None:
        self.seen: list[Any] = []

    def to_retrieval(self, args: Any) -> str | None:
        self.seen.append(args)
        return "https://platform/search"

    def to_item(self, payload: Any, within: str | None) -> str | None:
        return within


def test_the_arguments_a_tool_was_called_with_reach_what_keeps_its_result() -> None:
    """The query is in them, and a retrieval is addressed by its query."""
    links = _Args()
    retrieved = Retrieved(link=links)

    _after(retrieved, _result("OOMKilled"))

    assert links.seen == [{"query": "service:checkout status:error"}]


def test_a_failed_retrieval_is_still_refused_rather_than_addressed() -> None:
    """Nothing was retrieved, so there is nothing to go and look at."""
    links = _Args()
    retrieved = Retrieved(link=links)

    offered = _after(retrieved, {"isError": True, "content": []})

    assert offered["retrieval_failed"] is True
    assert links.seen == []
    assert retrieved.resolve("call-1") is None


def test_the_model_is_shown_no_address_it_could_copy_into_a_finding() -> None:
    """The one field a reader trusts most, kept out of the one place least trusted."""
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
