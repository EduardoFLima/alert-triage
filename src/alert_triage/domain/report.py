"""The TriageReport value: what the system has to say about one incident.

Deliberately thin, and deliberately channel-neutral. A subject and a body of
plain text are what every channel can carry, so rendering — a MIME message, a
card, whatever comes next — stays the adapter's own work and adding a channel
changes nothing about what a report *is*.

The incident travels with the report rather than being flattened into the
text: an identifier is what tells two reports apart, and what something later
attaches an acknowledgement to.
"""

from dataclasses import dataclass

from alert_triage.domain.incident import Incident


@dataclass(frozen=True)
class TriageReport:
    """What one incident is worth telling a team, before any channel sees it.

    Attributes:
        incident: The incident the report concerns.
        subject: One line announcing the report, as a subject or a heading.
        body: The report itself, as plain text. Opaque to delivery: a channel
            carries it unchanged, so changing what a report says never means
            adjusting a channel.
    """

    incident: Incident
    subject: str
    body: str

    def __post_init__(self) -> None:
        """Reject a subject no channel could present as the one line it is."""
        if not self.subject.strip():
            raise ValueError("A report needs a subject to announce it")
        if "\n" in self.subject or "\r" in self.subject:
            raise ValueError(
                "A report's subject is a single line: put the detail in the body"
            )

    @property
    def incident_id(self) -> str:
        """Identifier of the incident this report concerns."""
        return self.incident.id

    @property
    def service(self) -> str:
        """Service the incident is about."""
        return self.incident.service
