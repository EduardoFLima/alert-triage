"""What stops an investigation that is merely running long, and one that has hung.

Two stages, because those are two different failures needing two different
answers. A reasoning that is still working but slow should be told to stop
gathering and conclude on what it holds — it keeps its hypothesis, and that is
the common case. A reasoning that has stopped responding never reaches a
callback at all, so the only thing that can end it is a bound around the run.

The clock is injected rather than slept through: a test that waits five minutes
to establish a five-minute bound is a test nobody runs.
"""

from typing import Any

from pydantic import BaseModel

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.bounds import Bounds
from alert_triage.investigation.adapters.adk.consultation import (
    Consulted,
    bound_consultations_callback,
)
from alert_triage.investigation.adapters.adk.evidence import (
    Retrieved,
    keep_evidence_callback,
    log_tool_call,
)
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset

PERMITTED = frozenset({"search_datadog_logs"})


class _Reported(BaseModel):
    findings: list[dict[str, Any]] = []


class _Tool:
    def __init__(self, name: str = "search_datadog_logs") -> None:
        self.name = name


class _Hands:
    """A clock a test moves, in the monotonic seconds a deadline is measured in."""

    def __init__(self) -> None:
        self._seconds = 1000.0

    def __call__(self) -> float:
        return self._seconds

    def advance(self, seconds: float) -> None:
        self._seconds += seconds


CREW = (
    Specialist(
        name="logs_specialist",
        signal=Signal.LOGS,
        instruction="Look.",
        output_schema=_Reported,
        toolsets=(
            Toolset(provider="datadog", name="core", tools=("search_datadog_logs",)),
        ),
    ),
)


def _bounded(clock: _Hands, seconds: int = 300) -> Bounds:
    return Bounds(
        CircuitBreakers(max_investigation_duration_seconds=seconds), now=clock
    )


def _consult(consulted: Consulted, name: str = "logs_specialist") -> Any:
    return bound_consultations_callback(consulted)(
        tool=_Tool(name), args={"request": "look"}, tool_context=None
    )


def _call(caller: str, retrieved: Retrieved, bounds: Bounds) -> Any:
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


def test_a_consultation_after_the_deadline_is_declined() -> None:
    clock = _Hands()
    consulted = Consulted(
        offered=CREW, retrieved=Retrieved(), bounds=_bounded(clock, seconds=300)
    )
    assert _consult(consulted) is None
    consulted.record(CREW[0], {"findings": []})

    clock.advance(301)

    assert _consult(consulted) is not None


def test_the_reasoning_keeps_what_it_gathered_before_the_deadline() -> None:
    clock = _Hands()
    consulted = Consulted(
        offered=CREW, retrieved=Retrieved(), bounds=_bounded(clock, seconds=300)
    )
    _consult(consulted)
    consulted.record(CREW[0], {"findings": []})

    clock.advance(301)
    _consult(consulted)

    assert consulted.signals == (Signal.LOGS,)


def test_a_tool_call_after_the_deadline_is_declined() -> None:
    clock = _Hands()
    retrieved, bounds = Retrieved(), _bounded(clock, seconds=300)
    assert _call("logs_specialist", retrieved, bounds) is None

    clock.advance(301)

    assert _call("logs_specialist", retrieved, bounds) is not None


def test_time_running_out_declines_a_specialist_with_calls_still_left() -> None:
    """A budget unspent is not permission to spend it after the bound."""
    clock = _Hands()
    bounds = Bounds(
        CircuitBreakers(
            max_tool_calls_per_agent=8, max_investigation_duration_seconds=300
        ),
        now=clock,
    )

    clock.advance(301)

    assert _call("logs_specialist", Retrieved(), bounds) is not None


def test_what_time_declines_says_the_call_did_not_happen() -> None:
    """Time is not a platform that answered with nothing in it."""
    clock = _Hands()
    retrieved, bounds = Retrieved(), _bounded(clock, seconds=300)
    clock.advance(301)

    declined = _call("logs_specialist", retrieved, bounds)

    assert declined is not None
    read_as = declined["read_this_as"]
    assert "did not happen" in read_as
    assert "not" in read_as and "nothing" in read_as


def test_what_time_declines_at_the_manager_says_the_same() -> None:
    clock = _Hands()
    consulted = Consulted(
        offered=CREW, retrieved=Retrieved(), bounds=_bounded(clock, seconds=300)
    )
    clock.advance(301)

    refused = _consult(consulted)

    assert refused is not None
    read_as = refused["read_this_as"]
    assert "did not happen" in read_as
    assert "not" in read_as and "nothing" in read_as


def test_the_deadline_is_recorded_as_the_bound_that_was_reached() -> None:
    clock = _Hands()
    bounds = _bounded(clock, seconds=300)
    clock.advance(301)

    _call("logs_specialist", Retrieved(), bounds)

    assert bounds.reached
    assert "300 seconds" in bounds.reached[0]


def test_an_investigation_inside_its_bound_declines_nothing() -> None:
    """Nothing recorded about time, and no incompleteness carried from it."""
    clock = _Hands()
    retrieved, bounds = Retrieved(), _bounded(clock, seconds=300)
    consulted = Consulted(offered=CREW, retrieved=retrieved, bounds=bounds)

    clock.advance(299)

    assert _consult(consulted) is None
    assert _call("logs_specialist", retrieved, bounds) is None
    assert bounds.reached == ()
    assert retrieved.failures == ()
    assert consulted.refusals == ()


def test_an_unconfigured_investigation_is_bounded_by_the_documented_default() -> None:
    clock = _Hands()
    bounds = Bounds(now=clock)

    clock.advance(CircuitBreakers.DEFAULT_MAX_INVESTIGATION_DURATION_SECONDS + 1)

    assert _call("logs_specialist", Retrieved(), bounds) is not None
