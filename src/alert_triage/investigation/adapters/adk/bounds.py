"""The circuit breakers as one investigation actually enforces them.

Multi-agent reasoning runs away in three distinct ways, and each is bounded
independently here: inside one specialist's tool-calling loop, across the
manager's consultations, or by simply running long. One instance per
investigation, beside ``Retrieved`` and ``Consulted``, because a bound is spent
by an incident rather than by a deployment: what one investigation may still do
is not what the next one may.

Every bound is enforced by declining the call rather than by counting after it.
The seat is what makes that possible — ``before_tool_callback`` can answer a
call instead of making it — and a coordinator tallying afterwards has already
paid for the reasoning it wanted to prevent.

What is declined is answered in the register ``RETRIEVAL_FAILED`` and
``CONSULTATION_REFUSED`` are written in, for the same reason: the one thing that
must not happen is a model reading "we stopped looking" as "there was nothing to
find", and a terse error is exactly what invites that reading.

Which bounds an investigation reached is kept here too, so that a report can say
what stopped it rather than only that it was incomplete. An investigation that
looked everywhere and found little and one that was stopped before it could look
are different pieces of news.
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
    "service may be concluded from it in either direction. Report what the "
    "calls that did happen show."
)
"""What a specialist is handed in place of a call a bound will not permit.

Deliberately verbose, for the reason ``RETRIEVAL_FAILED`` is: a bound that reads
as an empty result is how "we stopped looking" becomes "there was nothing to
find", and that misreading is the one this whole register exists to prevent.
"""

Clock = Callable[[], float]
"""How this investigation reads the time, in seconds that only ever move forward.

Monotonic rather than wall-clock, so an adjustment to the machine's clock
mid-investigation can neither trip a bound early nor defer one indefinitely.
Injected so a test can drive a deadline without sleeping through one.
"""


class Bounds:
    """What one investigation may still do, and which bounds it has reached.

    One instance per investigation. It holds the configured breakers, the
    deadline computed when the investigation started, and the tool calls each
    specialist has spent — all three being facts about this incident rather than
    about the deployment, which is why they are not read off the configuration
    each time.
    """

    def __init__(
        self, breakers: CircuitBreakers | None = None, now: Clock = time.monotonic
    ) -> None:
        """Start an investigation bounded as this deployment configured it.

        Args:
            breakers: The bounds to enforce. Absent, the documented defaults:
                an unconfigured deployment is bounded by them rather than
                unbounded, which is the one outcome a breaker exists to prevent.
            now: How the deadline is measured, in monotonic seconds.
        """
        self._breakers = breakers or CircuitBreakers()
        self._now = now
        self._expires = now() + self._breakers.max_investigation_duration_seconds
        self._calls: dict[str, int] = {}
        self._reached: list[str] = []

    @property
    def hops(self) -> int:
        """How many specialist consultations this investigation may make.

        Read by both the manager's instruction and the callback that enforces
        it, so the number the reasoning plans against and the number it is held
        to cannot disagree.
        """
        return self._breakers.max_agent_hops

    @property
    def out_of_time(self) -> bool:
        """Whether this investigation's wall-clock bound has elapsed."""
        return self._now() >= self._expires

    @property
    def duration(self) -> int:
        """How long this investigation was given in total, in seconds."""
        return self._breakers.max_investigation_duration_seconds

    @property
    def remaining(self) -> float:
        """How long it has left, never negative so a bound already reached is zero."""
        return max(0.0, self._expires - self._now())

    @property
    def reached(self) -> tuple[str, ...]:
        """Which bounds this investigation reached, in the order it reached them.

        Empty is an investigation that ran within every bound it was given.
        Anything here is why its account is shorter than it wanted to be.
        """
        return tuple(self._reached)

    def reach(self, bound: str) -> str:
        """Record that a bound was reached, and say so in a reader's terms.

        Args:
            bound: What stopped the investigation, named as a reader would say
                it rather than as the setting is spelled.

        Returns:
            The same reason, so a caller can hand it on to whatever it is
            answering.
        """
        self._reached.append(bound)
        _log.warning(journal.event("a bound was reached", detail=bound))
        return bound

    def decline_consultation(self, name: str, spent: int) -> str | None:
        """Whether one more specialist may be consulted, and why not.

        Args:
            name: The specialist the reasoning is asking for.
            spent: How many consultations this investigation has already made.

        Returns:
            ``None`` where the consultation may be made, or why it may not.
            Time is checked first: a budget still unspent is not permission to
            spend it after the investigation's bound has elapsed.
        """
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
        """Whether this specialist may make one more tool call, and why not.

        The count is per specialist and cumulative across every consultation of
        it within this investigation: an agent is built once and reused, and
        resetting per consultation would give a specialist asked five times five
        full budgets — the runaway this bound exists to stop, wearing a
        different shape.

        Args:
            caller: The specialist about to call the platform.

        Returns:
            ``None`` where the call may be made, or why it may not. Time is
            checked first: a specialist with calls left still has none once the
            investigation is out of time.
        """
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
