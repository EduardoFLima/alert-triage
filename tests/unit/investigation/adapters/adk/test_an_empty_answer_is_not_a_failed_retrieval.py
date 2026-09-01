"""The gate this change turns on: silence from the platform is an answer.

A specialist asks about a signal a deployment may not have — a container
workload for a service running on virtual machines, traces for a service
nobody instrumented — and the platform answers that there are none. That is a
fact about the deployment, not a retrieval that failed, and recording it as
one would mark every investigation on such a deployment incomplete.

The opposite direction is the other half of the discipline and is asserted
beside it: a refusal, an error, and an answer carrying nothing readable stay
failures, because a broken search read as silence is the more dangerous
misreading.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.evidence import (
    Retrieved,
    keep_evidence_callback,
)
from alert_triage.investigation.adapters.adk.investigator import AdkInvestigator
from alert_triage.investigation.contract import InvestigationTarget, Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset
from alert_triage.shared.window import Window

PERMITTED = frozenset({"search_datadog_k8s_resources"})

EMPTY_ANSWERS: dict[str, Any] = {
    "an empty structured collection": {
        "content": [{"type": "text", "text": "[]"}],
        "structuredContent": {"result": []},
        "isError": False,
    },
    "an empty list of entries": [],
    "no content at all": {"content": [], "isError": False},
}
"""The shapes a platform answers "there are none" in."""


NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


class _Reported(BaseModel):
    findings: list[str] = []


def _target() -> InvestigationTarget:
    return InvestigationTarget(
        service="checkout", window=Window(start=NOON, end=NOON), alert_count=1
    )


def _asks_about_containers() -> Specialist:
    """A specialist whose signal a deployment may genuinely not have."""
    return Specialist(
        name="infrastructure_specialist",
        signal=Signal.LOGS,
        instruction="Look at what the service runs on.",
        output_schema=_Reported,
        toolsets=(Toolset(name="kubernetes", tools=("search_datadog_k8s_resources",)),),
    )


class _Tool:
    def __init__(self, name: str = "search_datadog_k8s_resources") -> None:
        self.name = name


def _after(retrieved: Retrieved, response: Any) -> Any:
    return keep_evidence_callback(retrieved, PERMITTED, "logs_specialist")(
        tool=_Tool(),
        args={"service": "checkout"},
        tool_context=None,
        tool_response=response,
    )


def _investigation_retrieving(answer: Any) -> Any:
    """A manager consulting one specialist whose retrieval comes back with that."""

    def _run(crew: Any, consulted: Any, retrieved: Retrieved, prompt: str) -> Any:
        for specialist in crew:
            _after(retrieved, answer)
            consulted.record(specialist, {"findings": []})
        return {"hypothesis": "", "confidence": "low"}

    return _run


def _worded(brief: str) -> dict[str, Any]:
    return {"headline": "checkout: nothing notable", "narrative": "Nothing found."}


def test_an_empty_answer_is_retained_as_a_retrieval_that_found_nothing() -> None:
    for shape, answer in EMPTY_ANSWERS.items():
        retrieved = Retrieved()

        offered = _after(retrieved, answer)

        assert retrieved.retrievals == 1, shape
        assert retrieved.failures == (), shape
        assert offered.get("retrieval_failed") is None, shape


def test_an_empty_answer_offers_the_model_no_items_to_cite() -> None:
    """Nothing came back, so there is nothing in it to point at."""
    retrieved = Retrieved()

    offered = _after(retrieved, EMPTY_ANSWERS["no content at all"])

    assert offered["call"] == "call-1"
    assert offered["items"] == []


def test_a_signal_the_deployment_does_not_have_leaves_the_investigation_complete() -> (
    None
):
    """A service that is not on containers is not an investigation that broke."""
    for shape, answer in EMPTY_ANSWERS.items():
        investigator = AdkInvestigator(
            crew=(_asks_about_containers(),),
            run_diagnostician=_investigation_retrieving(answer),
            run_report=_worded,
        )

        findings = investigator.investigate(_target()).findings

        assert findings.complete, shape
        assert findings.retrieval_failures == (), shape
        assert findings.findings == (), shape


def test_an_empty_answer_and_a_refused_one_stay_distinguishable() -> None:
    retrieved = Retrieved()

    _after(retrieved, EMPTY_ANSWERS["no content at all"])
    _after(retrieved, {"content": [{"type": "text", "text": "403"}], "isError": True})

    assert retrieved.retrievals == 1
    assert len(retrieved.failures) == 1


def test_an_answer_carrying_nothing_readable_is_still_a_failure() -> None:
    """The system cannot tell a broken answer from an empty one, so it says so."""
    for shape in (None, {"content": [{"type": "text", "text": "   "}]}):
        retrieved = Retrieved()

        offered = _after(retrieved, shape)

        assert offered["retrieval_failed"] is True, shape
        assert retrieved.failures, shape
