from dataclasses import dataclass


@dataclass(frozen=True)
class TriageReport:
    incident_id: str
    service: str
    subject: str
    body: str

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("A report needs a subject to announce it")
        if "\n" in self.subject or "\r" in self.subject:
            raise ValueError(
                "A report's subject is a single line: put the detail in the body"
            )
