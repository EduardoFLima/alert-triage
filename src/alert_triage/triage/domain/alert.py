"""The Alert entity: one incoming alert, in this project's own vocabulary."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Alert:
    """A single alert, independent of the platform that reported it.

    Grouping reasons about the service tag and the timestamp alone. The
    remaining fields are what a report needs to name which alerts fired and
    point a human at them; they default to empty so that a caller with nothing
    to report — grouping tests, a source that cannot supply provenance — is not
    forced to invent values.

    Attributes:
        service: Tag identifying the service the alert belongs to.
        fired_at: When the alert fired.
        source_id: The reporting platform's identifier for this alert, stable
            across runs so the same alert is recognisable when seen again.
        title: The alert's own title, as the platform reported it.
        link: URL at which a human can open the alert in that platform.
    """

    service: str
    fired_at: datetime
    source_id: str = ""
    title: str = ""
    link: str = ""
