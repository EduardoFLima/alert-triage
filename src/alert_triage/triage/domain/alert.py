from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Alert:
    """Provenance fields default empty so callers need not invent what they lack."""

    service: str
    fired_at: datetime
    source_id: str = ""
    title: str = ""
    link: str = ""
