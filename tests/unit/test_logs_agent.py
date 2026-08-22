from datetime import UTC, datetime, timedelta

from alert_triage.adapters.adk.credentials import ApiKey
from alert_triage.adapters.adk.logs_agent import (
    LOGS_INSTRUCTION,
    LogsFinding,
    ReportedFindings,
    build_logs_agent,
    describe,
)
from alert_triage.adapters.adk.model import build_model
from alert_triage.domain.alert import Alert
from alert_triage.domain.findings import MAX_EXAMPLES_PER_FINDING
from alert_triage.domain.incident import Incident

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _incident() -> Incident:
    return Incident(
        id="incident-1",
        service="checkout",
        alerts=(
            Alert(service="checkout", fired_at=NOON, source_id="a"),
            Alert(
                service="checkout", fired_at=NOON + timedelta(minutes=7), source_id="b"
            ),
        ),
    )


def test_the_instruction_asks_for_errors_and_warnings() -> None:
    assert "error" in LOGS_INSTRUCTION.lower()
    assert "warning" in LOGS_INSTRUCTION.lower()


def test_the_instruction_requires_a_citation_for_every_observation() -> None:
    assert "cite" in LOGS_INSTRUCTION.lower()


def test_the_instruction_bounds_the_examples_it_asks_for() -> None:
    assert str(MAX_EXAMPLES_PER_FINDING) in LOGS_INSTRUCTION


def test_the_instruction_forbids_naming_a_root_cause() -> None:
    """Slice 6 observes; concluding is the Diagnostician's job in slice 8."""
    assert "root cause" in LOGS_INSTRUCTION.lower()


def test_the_instruction_says_nothing_about_datadog() -> None:
    """A second platform behind the port must not mean rewriting the agent."""
    assert "datadog" not in LOGS_INSTRUCTION.lower()


def test_the_schema_offers_the_model_no_place_to_write_evidence() -> None:
    """It may cite a record; it may not compose one."""
    fields = set(LogsFinding.model_fields)

    assert fields == {"observation", "occurrences", "cites"}


def test_the_schema_carries_a_list_of_findings() -> None:
    assert set(ReportedFindings.model_fields) == {"findings"}


def test_an_incident_is_described_by_its_service_and_window() -> None:
    described = describe(_incident())

    assert "checkout" in described
    assert NOON.isoformat() in described
    assert (NOON + timedelta(minutes=7)).isoformat() in described


def test_the_agent_is_given_the_ports_tool_and_no_other() -> None:
    def _search(service: str, start: str, end: str, query: str) -> list[dict[str, str]]:
        return []

    agent = build_logs_agent(model="a-model", search_logs=_search)

    assert [getattr(tool, "__name__", None) for tool in agent.tools] == ["_search"]


def test_the_agent_runs_on_the_configured_model() -> None:
    def _search(service: str, start: str, end: str, query: str) -> list[dict[str, str]]:
        return []

    assert build_logs_agent(model="a-model", search_logs=_search).model == "a-model"


def test_the_agent_reports_through_the_findings_schema() -> None:
    def _search(service: str, start: str, end: str, query: str) -> list[dict[str, str]]:
        return []

    agent = build_logs_agent(model="a-model", search_logs=_search)

    assert agent.output_schema is ReportedFindings


def test_the_agent_accepts_a_model_already_built() -> None:
    """Told how to authenticate elsewhere; the specialist only reasons with it."""

    def _search(service: str, start: str, end: str, query: str) -> list[dict[str, str]]:
        return []

    reasoner = build_model("a-model", ApiKey("model-key"))

    assert build_logs_agent(model=reasoner, search_logs=_search).model is reasoner
