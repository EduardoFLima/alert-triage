from typing import Any

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.bounds import Bounds
from alert_triage.investigation.adapters.adk.evidence import Retrieved, log_tool_call

PERMITTED = frozenset({"search_datadog_logs"})

ANSWER_TOOL = "set_model_response"


class _Tool:
    def __init__(self, name: str = "search_datadog_logs") -> None:
        self.name = name


def _bounds(calls: int) -> Bounds:
    return Bounds(CircuitBreakers(max_tool_calls_per_agent=calls))


def _call(name: str, retrieved: Retrieved, bounds: Bounds) -> dict[str, Any] | None:
    return log_tool_call("logs_specialist", PERMITTED, retrieved, bounds)(
        tool=_Tool(name), args={"query": "status:error"}, tool_context=None
    )


def test_a_specialist_that_spent_its_calls_may_still_give_its_answer() -> None:
    retrieved, bounds = Retrieved(), _bounds(1)
    _call("search_datadog_logs", retrieved, bounds)

    assert _call("search_datadog_logs", retrieved, bounds) is not None
    assert _call(ANSWER_TOOL, retrieved, bounds) is None


def test_answering_does_not_spend_a_call_the_platform_could_have_had() -> None:
    retrieved, bounds = Retrieved(), _bounds(2)

    for _ in range(3):
        _call(ANSWER_TOOL, retrieved, bounds)

    assert _call("search_datadog_logs", retrieved, bounds) is None
    assert _call("search_datadog_logs", retrieved, bounds) is None


def test_answering_is_never_recorded_as_a_retrieval_that_failed() -> None:
    retrieved, bounds = Retrieved(), _bounds(0)

    _call(ANSWER_TOOL, retrieved, bounds)

    assert retrieved.failures == ()
    assert bounds.reached == ()


def test_a_declined_search_tells_the_specialist_to_answer_with_what_it_has() -> None:
    retrieved, bounds = Retrieved(), _bounds(0)

    declined = _call("search_datadog_logs", retrieved, bounds)

    assert declined is not None
    read_as = declined["read_this_as"]
    assert "final answer" in read_as
