from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from alert_triage.adapters.adk.investigator import AdkInvestigator
from alert_triage.domain.alert import Alert
from alert_triage.domain.findings import LogRecord, Signal
from alert_triage.domain.incident import Incident
from alert_triage.domain.window import Window
from alert_triage.ports.investigator import InvestigatorError
from alert_triage.ports.observability_platform import ObservabilityPlatformError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _incident() -> Incident:
    return Incident(
        id="incident-1",
        service="checkout",
        alerts=(Alert(service="checkout", fired_at=NOON, source_id="a"),),
    )


class _Platform:
    """A platform that answers with canned records, or refuses."""

    def __init__(
        self, records: Sequence[LogRecord] = (), failure: str | None = None
    ) -> None:
        self.records = records
        self.failure = failure
        self.asked: list[tuple[str, Window, str]] = []

    def search_logs(
        self, service: str, window: Window, query: str
    ) -> Sequence[LogRecord]:
        self.asked.append((service, window, query))
        if self.failure is not None:
            raise ObservabilityPlatformError(self.failure)
        return self.records


def _record(message: str = "container OOMKilled") -> LogRecord:
    return LogRecord(timestamp=NOON, level="ERROR", message=message, service="checkout")


def _agent_that(
    *, searches: bool = True, reports: list[dict[str, Any]] | None = None
) -> Any:
    """A stand-in for the model: it calls the tool, then reports what we say."""

    def _run(tool: Any, prompt: str) -> dict[str, Any]:
        if searches:
            tool("checkout", NOON.isoformat(), NOON.isoformat(), "status:error")
        return {"findings": reports if reports is not None else []}

    return _run


def test_findings_are_built_from_what_the_platform_returned() -> None:
    platform = _Platform([_record()])
    investigator = AdkInvestigator(
        platform=platform,
        run_agent=_agent_that(
            reports=[
                {
                    "observation": "OOMKilled recurs",
                    "occurrences": 5,
                    "cites": ["rec_1"],
                }
            ]
        ),
    )

    findings = investigator.investigate(_incident())

    (finding,) = findings.findings
    assert finding.signal is Signal.LOGS
    assert finding.examples == (_record(),)


def test_the_search_is_asked_about_the_incidents_service_and_window() -> None:
    platform = _Platform([_record()])
    investigator = AdkInvestigator(platform=platform, run_agent=_agent_that())

    investigator.investigate(_incident())

    (service, window, _query) = platform.asked[0]
    assert service == "checkout"
    assert window == _incident().window


def test_an_investigation_that_found_nothing_returns_empty_findings() -> None:
    investigator = AdkInvestigator(platform=_Platform(), run_agent=_agent_that())

    findings = investigator.investigate(_incident())

    assert findings.findings == ()
    assert not findings.anything_notable


def test_a_platform_failure_becomes_an_investigator_failure() -> None:
    """'We could not look' must never reach a caller as 'we looked and it is clean'."""
    platform = _Platform(failure="the platform is unreachable")
    investigator = AdkInvestigator(platform=platform, run_agent=_agent_that())

    with pytest.raises(InvestigatorError, match="unreachable"):
        investigator.investigate(_incident())


def test_a_model_failure_becomes_an_investigator_failure() -> None:
    def _explodes(tool: Any, prompt: str) -> dict[str, Any]:
        raise RuntimeError("the model refused")

    investigator = AdkInvestigator(platform=_Platform(), run_agent=_explodes)

    with pytest.raises(InvestigatorError, match="refused"):
        investigator.investigate(_incident())


def test_a_fabricated_citation_does_not_reach_the_findings() -> None:
    platform = _Platform([_record()])
    investigator = AdkInvestigator(
        platform=platform,
        run_agent=_agent_that(
            reports=[
                {"observation": "invented", "occurrences": 9, "cites": ["rec_99"]},
            ]
        ),
    )

    assert investigator.investigate(_incident()).findings == ()


def test_a_search_the_model_never_made_leaves_nothing_citable() -> None:
    platform = _Platform([_record()])
    investigator = AdkInvestigator(
        platform=platform,
        run_agent=_agent_that(
            searches=False,
            reports=[{"observation": "guessed", "occurrences": 1, "cites": ["rec_1"]}],
        ),
    )

    assert investigator.investigate(_incident()).findings == ()
    assert platform.asked == []


def test_the_records_offered_to_the_model_carry_citable_identifiers() -> None:
    platform = _Platform([_record("first"), _record("second")])
    offered: list[Any] = []

    def _capture(tool: Any, prompt: str) -> dict[str, Any]:
        offered.extend(tool("checkout", NOON.isoformat(), NOON.isoformat(), "*"))
        return {"findings": []}

    AdkInvestigator(platform=platform, run_agent=_capture).investigate(_incident())

    assert [one["id"] for one in offered] == ["rec_1", "rec_2"]
    assert [one["message"] for one in offered] == ["first", "second"]


def test_each_investigation_starts_with_nothing_citable() -> None:
    """An identifier from an earlier incident must not resolve in a later one."""
    platform = _Platform([_record()])
    investigator = AdkInvestigator(
        platform=platform,
        run_agent=_agent_that(
            searches=False,
            reports=[{"observation": "stale", "occurrences": 1, "cites": ["rec_1"]}],
        ),
    )

    assert investigator.investigate(_incident()).findings == ()
