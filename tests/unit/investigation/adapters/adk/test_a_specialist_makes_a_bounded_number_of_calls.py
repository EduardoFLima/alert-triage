"""How many times one specialist may reach the platform, and what stops it.

A specialist with six tools and runtime discovery of what they take can loop
indefinitely: nothing about a search failing, or coming back empty, tells a
model to stop searching. The bound is what stops it, and it is spent per
specialist per incident rather than per consultation — an agent is built once
and reused, so resetting the count each time the manager comes back would hand a
specialist asked five times five full budgets.

What a declined call is answered with matters more than that it is declined. A
bound that reads as a platform with nothing in it is how "we stopped looking"
becomes "there was nothing to find", which is the misreading the whole refusal
register exists to prevent.
"""

import logging
from typing import Any

import pytest

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.bounds import Bounds
from alert_triage.investigation.adapters.adk.evidence import (
    Retrieved,
    keep_evidence_callback,
    log_tool_call,
)
from alert_triage.investigation.contract import Findings
from alert_triage.investigation.domain.evidence import RETRIEVAL_FAILED

PERMITTED = frozenset({"search_datadog_logs"})


class _Tool:
    def __init__(self, name: str = "search_datadog_logs") -> None:
        self.name = name


def _bounds(calls: int) -> Bounds:
    return Bounds(CircuitBreakers(max_tool_calls_per_agent=calls))


def _call(caller: str, retrieved: Retrieved, bounds: Bounds) -> dict[str, Any] | None:
    """One tool call, driven the way the framework drives one."""
    declined = log_tool_call(caller, retrieved, bounds)(
        tool=_Tool(), args={"query": "status:error"}, tool_context=None
    )
    if declined is None:
        keep_evidence_callback(retrieved, PERMITTED, caller)(
            tool=_Tool(),
            args={"query": "status:error"},
            tool_context=None,
            tool_response={"logs": [{"message": "OOMKilled"}]},
        )
    return declined


def test_a_specialist_calling_past_its_bound_has_the_further_calls_declined() -> None:
    retrieved, bounds = Retrieved(), _bounds(2)

    permitted = [_call("logs_specialist", retrieved, bounds) for _ in range(2)]
    declined = _call("logs_specialist", retrieved, bounds)

    assert permitted == [None, None]
    assert declined is not None


def test_it_still_reports_on_the_evidence_it_gathered_before_the_bound() -> None:
    """The searches that came back are no less true for the budget running out."""
    retrieved, bounds = Retrieved(), _bounds(2)
    for _ in range(3):
        _call("logs_specialist", retrieved, bounds)

    assert retrieved.retrievals == 2
    assert retrieved.resolve("call-2") is not None


def test_an_unconfigured_specialist_is_bounded_by_the_documented_default() -> None:
    retrieved, bounds = Retrieved(), Bounds()
    for _ in range(CircuitBreakers.DEFAULT_MAX_TOOL_CALLS_PER_AGENT):
        _call("logs_specialist", retrieved, bounds)

    assert _call("logs_specialist", retrieved, bounds) is not None


def test_a_declined_call_says_the_call_did_not_happen() -> None:
    """Not that the platform answered: those are opposite pieces of news."""
    retrieved, bounds = Retrieved(), _bounds(0)

    declined = _call("logs_specialist", retrieved, bounds)

    assert declined is not None
    read_as = declined["read_this_as"]
    assert "did not happen" in read_as
    assert "not" in read_as and "nothing" in read_as
    assert read_as != RETRIEVAL_FAILED


def test_a_declined_call_is_not_a_retrieval_that_came_back_empty() -> None:
    retrieved, bounds = Retrieved(), _bounds(0)

    _call("logs_specialist", retrieved, bounds)

    assert retrieved.retrievals == 0
    assert retrieved.resolve("call-1") is None


def test_the_count_is_cumulative_across_two_consultations_of_one_specialist() -> None:
    """An agent is built once per investigation, so its budget is spent once."""
    retrieved, bounds = Retrieved(), _bounds(3)

    first = [_call("logs_specialist", retrieved, bounds) for _ in range(2)]
    second = [_call("logs_specialist", retrieved, bounds) for _ in range(2)]

    assert first == [None, None]
    assert second[0] is None
    assert second[1] is not None


def test_one_specialist_reaching_its_bound_leaves_another_its_full_number() -> None:
    retrieved, bounds = Retrieved(), _bounds(1)
    _call("logs_specialist", retrieved, bounds)

    assert _call("logs_specialist", retrieved, bounds) is not None
    assert _call("apm_specialist", retrieved, bounds) is None


def test_a_declined_call_is_recorded_so_the_investigation_reads_as_incomplete() -> None:
    retrieved, bounds = Retrieved(), _bounds(0)

    _call("logs_specialist", retrieved, bounds)

    findings = Findings(retrieval_failures=retrieved.failures)
    assert findings.retrieval_failures
    assert "logs_specialist" in findings.retrieval_failures[0]


def test_the_bound_that_was_reached_is_recorded_as_one() -> None:
    """A report has to say what stopped it, not only that it was stopped."""
    retrieved, bounds = Retrieved(), _bounds(0)

    _call("logs_specialist", retrieved, bounds)

    assert bounds.reached
    assert "calls" in bounds.reached[0]


def test_a_permitted_call_is_still_written_down_before_it_is_made(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Bounding the seat did not cost it the account it was already keeping."""
    from alert_triage.investigation.adapters.adk.evidence import TOOL_CALL_LOGGER

    with caplog.at_level(logging.INFO, logger=TOOL_CALL_LOGGER):
        declined = log_tool_call("logs_specialist", Retrieved(), _bounds(1))(
            tool=_Tool(), args={"query": "status:error"}, tool_context=None
        )

    assert declined is None
    assert "logs_specialist" in caplog.text
    assert "search_datadog_logs" in caplog.text
