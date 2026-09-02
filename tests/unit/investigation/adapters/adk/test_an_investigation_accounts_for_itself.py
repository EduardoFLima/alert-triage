"""What an investigation writes down as it happens, for whoever reads it after.

An investigation is the part of a run nobody can reconstruct afterwards: which
specialist was asked, what it was asked for, what the platform actually
answered, and what the specialist made of it. Each of those is written down at
the moment it happens, and the observation — the one thing a human came to
read — is never shortened.
"""

import logging
from typing import Any

import pytest
from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.consultation import (
    Consulted,
    bound_consultations_callback,
    collect_findings_callback,
)
from alert_triage.investigation.adapters.adk.evidence import (
    TOOL_CALL_LOGGER,
    Retrieved,
    keep_evidence_callback,
    log_tool_call,
)
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset

PERMITTED = frozenset({"search_datadog_logs"})

OBSERVED = (
    "The checkout pods are OOM-killed repeatedly from 09:14 onward, and the "
    "first kill lands ninety seconds after the deploy event that appears in "
    "the same stream. Thirty-one of the thirty-seven error lines in the "
    "window are that same kill, against three different pod identities, so "
    "this is the whole replica set rather than one unlucky host."
)


class _Reported(BaseModel):
    findings: list[dict[str, Any]] = []


class _Tool:
    def __init__(self, name: str) -> None:
        self.name = name


def _specialist() -> Specialist:
    return Specialist(
        name="logs_specialist",
        signal=Signal.LOGS,
        instruction="Look at the logs.",
        output_schema=_Reported,
        toolsets=(
            Toolset(provider="datadog", name="core", tools=("search_datadog_logs",)),
        ),
    )


def _consulted() -> Consulted:
    retrieved = Retrieved()
    retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})
    return Consulted(offered=(_specialist(),), retrieved=retrieved)


def _reporting(observation: str) -> dict[str, Any]:
    return {
        "findings": [
            {
                "observation": observation,
                "occurrences": 31,
                "cites": ["call-1/item-1"],
            }
        ]
    }


def test_a_consultation_is_written_down_with_what_it_asked_for(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        bound_consultations_callback(_consulted())(
            tool=_Tool("logs_specialist"),
            args={"request": "What changed around 09:14?"},
            tool_context=None,
        )

    assert "consulting logs_specialist" in caplog.text
    assert "What changed around 09:14?" in caplog.text


def test_what_a_specialist_observed_is_written_down_whole(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The investigation's own words. Half of an observation is worse than none."""
    with caplog.at_level(logging.INFO):
        collect_findings_callback(_consulted())(
            tool=_Tool("logs_specialist"),
            args={"request": "look at the logs"},
            tool_context=None,
            tool_response=_reporting(OBSERVED),
        )

    assert OBSERVED in " ".join(caplog.text.split())


def test_a_specialist_that_bore_nothing_out_is_written_down_as_that(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Silence here would read as a specialist nobody asked."""
    with caplog.at_level(logging.INFO):
        collect_findings_callback(_consulted())(
            tool=_Tool("logs_specialist"),
            args={"request": "look at the logs"},
            tool_context=None,
            tool_response={"findings": []},
        )

    assert "logs_specialist" in caplog.text
    assert "nothing" in caplog.text


def test_a_report_nothing_can_be_read_out_of_is_written_down_as_that(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        collect_findings_callback(_consulted())(
            tool=_Tool("logs_specialist"),
            args={"request": "look at the logs"},
            tool_context=None,
            tool_response="not a record at all",
        )

    assert "── a specialist reported something unreadable" in caplog.text


def test_a_tool_call_is_written_down_with_the_specialist_making_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=TOOL_CALL_LOGGER):
        log_tool_call("logs_specialist")(
            tool=_Tool("search_datadog_logs"),
            args={"query": "service:checkout status:error"},
            tool_context=None,
        )

    assert "logs_specialist" in caplog.text
    assert "search_datadog_logs" in caplog.text
    assert "service:checkout status:error" in caplog.text


def test_what_the_platform_answered_is_written_down_next_to_what_was_asked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=TOOL_CALL_LOGGER):
        keep_evidence_callback(Retrieved(), PERMITTED, "logs_specialist")(
            tool=_Tool("search_datadog_logs"),
            args={"query": "service:checkout"},
            tool_context=None,
            tool_response={"logs": [{"message": "OOMKilled"}, {"message": "restart"}]},
        )

    assert "search_datadog_logs" in caplog.text
    assert "call-1" in caplog.text
    assert "OOMKilled" in caplog.text


def test_a_platform_answer_too_long_to_read_is_shortened(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A single log search would otherwise be the whole run's output."""
    with caplog.at_level(logging.INFO, logger=TOOL_CALL_LOGGER):
        keep_evidence_callback(Retrieved(), PERMITTED, "logs_specialist")(
            tool=_Tool("search_datadog_logs"),
            args={"query": "service:checkout"},
            tool_context=None,
            tool_response={"logs": [{"message": "OOMKilled " * 200}]},
        )

    assert "more characters" in caplog.text
    assert len(caplog.text) < 2000


def test_an_answer_with_nothing_to_cite_within_it_is_not_written_down_as_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A flame graph has no items in it; "items 0" would read as a quiet platform."""
    with caplog.at_level(logging.INFO, logger=TOOL_CALL_LOGGER):
        keep_evidence_callback(Retrieved(), PERMITTED, "logs_specialist")(
            tool=_Tool("search_datadog_logs"),
            args={"query": "service:checkout"},
            tool_context=None,
            tool_response={"summary": "the whole window, aggregated"},
        )

    assert "cited as a whole" in caplog.text


def test_the_tool_back_and_forth_is_written_where_it_can_be_held_on_its_own(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A deployment that wants the account without the working turns off one name."""
    with caplog.at_level(logging.INFO, logger=TOOL_CALL_LOGGER):
        log_tool_call("logs_specialist")(
            tool=_Tool("search_datadog_logs"), args={}, tool_context=None
        )
        keep_evidence_callback(Retrieved(), PERMITTED, "logs_specialist")(
            tool=_Tool("search_datadog_logs"),
            args={},
            tool_context=None,
            tool_response={"logs": [{"message": "OOMKilled"}]},
        )

    assert {record.name for record in caplog.records} == {TOOL_CALL_LOGGER}


def test_a_failed_retrieval_is_still_the_investigations_own_business(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Turning the working off must not turn off the platform refusing to answer."""
    with caplog.at_level(logging.INFO):
        keep_evidence_callback(Retrieved(), PERMITTED, "logs_specialist")(
            tool=_Tool("search_datadog_logs"),
            args={},
            tool_context=None,
            tool_response={"error": "403"},
        )

    (record,) = caplog.records
    assert record.name != TOOL_CALL_LOGGER
    assert "403" in record.getMessage()


def test_a_failed_retrieval_is_not_written_down_as_an_answer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    retrieved = Retrieved()

    with caplog.at_level(logging.INFO):
        keep_evidence_callback(retrieved, PERMITTED, "logs_specialist")(
            tool=_Tool("search_datadog_logs"),
            args={"query": "service:checkout"},
            tool_context=None,
            tool_response={"error": "403"},
        )

    assert retrieved.retrievals == 0
    assert "403" in caplog.text
