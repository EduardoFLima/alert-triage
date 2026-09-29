from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Window:
    """A bounded period; a single-alert incident has ``start == end``."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("A window cannot end before it starts")
