"""The alert entity the rest of the domain reasons about."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Alert:
    """A single alert that fired, in this project's vocabulary.

    Deliberately free of any observability platform's wire format: an
    adapter translates a Datadog monitor event (or anything else) into this
    shape before the domain sees it.

    Attributes:
        service: The service tag the alert is attributed to. Grouping treats
            this as the identity of "what is broken".
        raised_at: When the alert fired, used to decide whether two alerts
            fall inside the same grouping window.
    """

    service: str
    raised_at: datetime
