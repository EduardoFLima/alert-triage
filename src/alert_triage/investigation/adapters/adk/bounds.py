"""Bounds that decline a call before it is made, rather than count it after.

A tally taken afterwards has already paid for the work it meant to prevent.
"""

import logging
import time
from collections.abc import Callable

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.shared import journal

_log = logging.getLogger(__name__)

CALL_DECLINED = (
    "This call did not happen. The investigation has reached a bound it may not "
    "cross, so the platform was never asked and has returned nothing. This is "
    "not a platform that answered with no results, and nothing about the "
    "service may be concluded from it in either direction. Stop searching and "
    "give your final answer now, in the shape you were asked for, reporting "
    "what the calls that did happen show."
)
"""Verbose so a bound is not mistaken for an empty platform answer.

It also tells the specialist to answer now: told only that a call failed, it
tries another, and runs out of turns in prose its output schema cannot parse.
"""

Clock = Callable[[], float]
"""Monotonic so wall-clock changes cannot move a deadline."""


class Bounds:
    def __init__(
        self, breakers: CircuitBreakers | None = None, now: Clock = time.monotonic
    ) -> None:
        self._breakers = breakers or CircuitBreakers()
        self._now = now
        self._expires = now() + self._breakers.max_investigation_duration_seconds
        self._calls: dict[str, int] = {}
        self._reached: list[str] = []

    @property
    def hops(self) -> int:
        """Read by prompt and callback so planned and enforced budgets match."""
        return self._breakers.max_agent_hops

    @property
    def out_of_time(self) -> bool:
        return self._now() >= self._expires

    @property
    def duration(self) -> int:
        return self._breakers.max_investigation_duration_seconds

    @property
    def remaining(self) -> float:
        return max(0.0, self._expires - self._now())

    @property
    def reached(self) -> tuple[str, ...]:
        """Empty means every bound held; otherwise this says why it is short."""
        return tuple(self._reached)

    def reach(self, bound: str) -> str:
        self._reached.append(bound)
        _log.warning(journal.event("a bound was reached", detail=bound))
        return bound

    def decline_consultation(self, name: str, spent: int) -> str | None:
        if self.out_of_time:
            return self.reach(
                f"the {name} was not consulted: this investigation reached its "
                f"{self._breakers.max_investigation_duration_seconds} seconds"
            )
        if spent >= self.hops:
            return self.reach(
                f"the {name} was not consulted: this investigation has spent "
                f"its {self.hops} consultations"
            )
        return None

    def decline_call(self, caller: str) -> str | None:
        """Counts span the investigation because reused agents would otherwise reset."""
        if self.out_of_time:
            return self.reach(
                f"{caller} stopped calling: this investigation reached its "
                f"{self._breakers.max_investigation_duration_seconds} seconds"
            )
        spent = self._calls.get(caller, 0)
        if spent >= self._breakers.max_tool_calls_per_agent:
            return self.reach(
                f"{caller} stopped calling: it has spent the "
                f"{self._breakers.max_tool_calls_per_agent} calls it is allowed"
            )
        self._calls[caller] = spent + 1
        return None
