import inspect
from dataclasses import dataclass, field
from datetime import UTC, datetime

from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.domain.incident import Incident
from alert_triage.triage.ports.ledger import TriageLedger, TriageLedgerError

NOON = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


@dataclass
class InMemoryTriageLedger:
    incidents: list[Incident] = field(default_factory=list)

    def open_incidents(self, service: str, now: datetime) -> list[Incident]:
        return [
            incident
            for incident in self.incidents
            if incident.service == service and incident.closed_at is None
        ]

    def record(self, incident: Incident, now: datetime) -> None:
        self.incidents = [held for held in self.incidents if held.id != incident.id]
        self.incidents.append(incident)


def _incident(incident_id: str = "incident-1", service: str = "checkout") -> Incident:
    return Incident(
        id=incident_id,
        service=service,
        alerts=(Alert(service=service, fired_at=NOON, source_id="a"),),
        last_reported_at=NOON,
    )


def test_the_port_hands_back_the_incidents_it_was_given() -> None:
    incident = _incident()
    ledger: TriageLedger = InMemoryTriageLedger()

    ledger.record(incident, NOON)

    on_record = ledger.open_incidents("checkout", NOON)
    assert isinstance(ledger, TriageLedger)
    assert on_record == [incident]
    assert all(isinstance(held, Incident) for held in on_record)


def test_a_service_with_nothing_on_record_is_a_success_not_a_failure() -> None:
    ledger: TriageLedger = InMemoryTriageLedger()

    assert ledger.open_incidents("checkout", NOON) == []


def test_the_ledger_is_synchronous() -> None:
    assert not inspect.iscoroutinefunction(InMemoryTriageLedger.record)
    assert not inspect.iscoroutinefunction(TriageLedger.open_incidents)
    assert not inspect.iscoroutinefunction(TriageLedger.record)


def test_a_ledger_failure_has_one_error_type_to_catch() -> None:
    assert issubclass(TriageLedgerError, Exception)


def test_the_port_speaks_only_the_domain_s_vocabulary() -> None:
    annotations = [
        parameter.annotation
        for method in (TriageLedger.open_incidents, TriageLedger.record)
        for parameter in inspect.signature(method).parameters.values()
    ]

    assert all(
        annotation in {inspect.Parameter.empty, str, datetime, Incident}
        for annotation in annotations
    ), annotations
