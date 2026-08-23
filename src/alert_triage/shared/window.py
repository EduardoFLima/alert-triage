"""The Window value: the stretch of time a question about an incident concerns.

An incident already knows when its earliest and latest alerts fired, so a
window is derived from it rather than stored beside it — two records of the
same fact can disagree, and only one of them can be right.

It lives in the shared kernel because it appears inside a domain type on both
sides of the investigation boundary. Duplicating it would duplicate its
invariant, and giving it to either context would make the other import across
a boundary for a time primitive. It is a value of its own rather than two loose
datetimes because passing those leaves argument order as the only thing
standing between "the last hour" and "the hour before time began".
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
