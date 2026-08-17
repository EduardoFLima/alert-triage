"""The Window value: the stretch of time a question about an incident concerns.

An incident already knows when its earliest and latest alerts fired, so a
window is derived from it rather than stored beside it — two records of the
same fact can disagree, and only one of them can be right.

It exists as a value of its own because it is what crosses the
``ObservabilityPlatform`` boundary: a specialist agent asks about a service
*over a period*, and passing two loose datetimes leaves the order of the
arguments as the only thing standing between "the last hour" and "the hour
before time began".
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Window:
    """A period of time, bounded at both ends.

    Attributes:
        start: When the period begins.
        end: When the period ends. Never earlier than ``start``, and equal to
            it for an incident of a single alert.
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        """Reject a window that runs backwards, which no query could satisfy."""
        if self.end < self.start:
            raise ValueError("A window cannot end before it starts")
