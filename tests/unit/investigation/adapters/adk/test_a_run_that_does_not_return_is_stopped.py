import asyncio
from typing import Any

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.bounds import Bounds
from alert_triage.investigation.adapters.adk.investigator import run_bounded


async def _hangs() -> dict[str, Any]:
    await asyncio.Event().wait()
    return {"hypothesis": "never reached", "confidence": "high"}


async def _answers() -> dict[str, Any]:
    return {"hypothesis": "the pods are out of memory", "confidence": "high"}


def _bounds(seconds: int) -> Bounds:
    return Bounds(CircuitBreakers(max_investigation_duration_seconds=seconds))


def test_a_run_that_does_not_return_is_stopped() -> None:
    concluded = asyncio.run(run_bounded(_hangs(), _bounds(seconds=0)))

    assert concluded == {}


def test_being_stopped_is_recorded_as_the_bound_that_was_reached() -> None:
    bounds = _bounds(seconds=0)

    asyncio.run(run_bounded(_hangs(), bounds))

    assert bounds.reached
    assert "0 seconds" in bounds.reached[0]


def test_a_run_that_answers_inside_its_bound_is_left_alone() -> None:
    bounds = _bounds(seconds=300)

    concluded = asyncio.run(run_bounded(_answers(), bounds))

    assert concluded == {
        "hypothesis": "the pods are out of memory",
        "confidence": "high",
    }
    assert bounds.reached == ()
