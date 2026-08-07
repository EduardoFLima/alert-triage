"""The Alert entity: one incoming alert, in this project's own vocabulary."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Alert:
    """A single alert, independent of the platform that reported it.

    Only the fields grouping reasons about are fixed here. An adapter
    translating a platform's wire format is free to carry richer payloads on
    its own types; what crosses into the domain is this.

    Attributes:
        service: Tag identifying the service the alert belongs to.
        fired_at: When the alert fired.
    """

    service: str
    fired_at: datetime
