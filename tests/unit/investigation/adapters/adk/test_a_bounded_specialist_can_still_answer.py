"""A specialist that has spent its calls must still be able to report what it found.

The bound is on reaching the platform. It is not on the specialist answering,
and the two arrive on the same seat.

Where a model cannot pair an output schema with tools, the framework does not
ask it for JSON — it injects a tool of its own, ``set_model_response``, and
tells the model to give its final answer by calling it. That call goes through
``before_tool_callback`` like any other. A seat that counts every call therefore
spends the budget on the specialist's own answer and, once the budget is gone,
declines the one call that was never a search: the specialist is left with no
way to produce its schema, falls back to prose, and the prose fails validation
on the way back through ``AgentTool`` — which costs the manager the whole
consultation and every finding behind it.

So the seat admits only the tools the declaration named, exactly as the seat
after it does.
"""

from typing import Any

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.bounds import Bounds
from alert_triage.investigation.adapters.adk.evidence import Retrieved, log_tool_call

PERMITTED = frozenset({"search_datadog_logs"})

ANSWER_TOOL = "set_model_response"
"""What ADK injects for an agent pairing an output schema with tools."""


class _Tool:
    def __init__(self, name: str = "search_datadog_logs") -> None:
        self.name = name


def _bounds(calls: int) -> Bounds:
    return Bounds(CircuitBreakers(max_tool_calls_per_agent=calls))


def _call(name: str, retrieved: Retrieved, bounds: Bounds) -> dict[str, Any] | None:
    """One tool call, driven the way the framework drives one."""
    return log_tool_call("logs_specialist", PERMITTED, retrieved, bounds)(
        tool=_Tool(name), args={"query": "status:error"}, tool_context=None
    )


def test_a_specialist_that_spent_its_calls_may_still_give_its_answer() -> None:
    """Declining this one leaves the specialist no way to report at all."""
    retrieved, bounds = Retrieved(), _bounds(1)
    _call("search_datadog_logs", retrieved, bounds)

    assert _call("search_datadog_logs", retrieved, bounds) is not None
    assert _call(ANSWER_TOOL, retrieved, bounds) is None


def test_answering_does_not_spend_a_call_the_platform_could_have_had() -> None:
    """The budget buys searches. A specialist does not pay to be heard."""
    retrieved, bounds = Retrieved(), _bounds(2)

    for _ in range(3):
        _call(ANSWER_TOOL, retrieved, bounds)

    assert _call("search_datadog_logs", retrieved, bounds) is None
    assert _call("search_datadog_logs", retrieved, bounds) is None


def test_answering_is_never_recorded_as_a_retrieval_that_failed() -> None:
    """A report saying the account is incomplete must mean a search was lost."""
    retrieved, bounds = Retrieved(), _bounds(0)

    _call(ANSWER_TOOL, retrieved, bounds)

    assert retrieved.failures == ()
    assert bounds.reached == ()


def test_a_declined_search_tells_the_specialist_to_answer_with_what_it_has() -> None:
    """Told only that the call failed, a model keeps trying rather than reporting."""
    retrieved, bounds = Retrieved(), _bounds(0)

    declined = _call("search_datadog_logs", retrieved, bounds)

    assert declined is not None
    read_as = declined["read_this_as"]
    assert "final answer" in read_as
