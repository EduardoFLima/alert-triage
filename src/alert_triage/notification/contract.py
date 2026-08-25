"""What notification publishes: the one thing it can be asked to deliver.

Deliberately thin, and deliberately channel-neutral. A subject and a body of
plain text are what every channel can carry, so rendering — a MIME message, a
card, whatever comes next — stays the adapter's own work and adding a channel
changes nothing about what a report *is*.

The incident is named rather than carried: an identifier is what tells two
reports apart, and what something later attaches an acknowledgement to. A
report holding the aggregate would make delivering one depend on what an
incident is, which is exactly what this context is spared.

Deciding what to say about an incident is the caller's; saying it is this
context's. So this holds the value and nothing that builds one.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TriageReport:
    """What one incident is worth telling a team, before any channel sees it.

    Attributes:
        incident_id: Identifier of the incident the report concerns.
        service: Service the incident is about.
        subject: One line announcing the report, as a subject or a heading.
        body: The report itself, as plain text. Opaque to delivery: a channel
            carries it unchanged, so changing what a report says never means
            adjusting a channel.
    """

    incident_id: str
    service: str
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
