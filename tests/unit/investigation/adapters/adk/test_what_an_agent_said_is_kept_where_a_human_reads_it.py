"""An agent's own words, on their way past to whoever is reading the log.

What the Diagnostician says between consultations is the account of why it
asked what it asked, and it is the one thing the consultation record does not
keep: that holds what was asked and what came back, not the thread joining
them. What the Report agent says is the report itself, taking shape. The
callback watches and never intervenes, so a run reads the same whether anyone
is listening or not.
"""

import logging
from typing import Any

import pytest

from alert_triage.investigation.adapters.adk.reasoning import log_reasoning


class _Part:
    """A stand-in for one part of the response ADK hands over."""

    def __init__(self, text: str | None = None) -> None:
        self.text = text


class _Content:
    def __init__(self, parts: list[_Part]) -> None:
        self.parts = parts


class _Response:
    """A stand-in for the model response, in the shapes ADK produces."""

    def __init__(
        self, parts: list[_Part] | None = None, *, partial: bool = False
    ) -> None:
        self.content = None if parts is None else _Content(parts)
        self.partial = partial


def _after(response: Any, agent: str = "diagnostician") -> Any:
    return log_reasoning(agent)(callback_context=None, llm_response=response)


def test_what_the_manager_says_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _after(_Response([_Part("Saturation, so I will ask the metrics specialist.")]))

    assert "Saturation, so I will ask the metrics specialist." in caplog.text


def test_the_agent_that_said_it_is_named(caplog: pytest.LogCaptureFixture) -> None:
    """Two agents reason in one investigation; an unattributed thought is noise."""
    with caplog.at_level(logging.INFO):
        _after(_Response([_Part("Two signals, one cause.")]), "report_writer")

    assert "report_writer" in caplog.text


def test_an_answer_given_in_a_schema_is_read_as_its_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An agent's last turn is its schema. Raw JSON is the thing being fixed here."""
    with caplog.at_level(logging.INFO):
        answered = '{"headline": "checkout is OOM-killing", "narrative": "At 09:14."}'
        _after(_Response([_Part(answered)]), "report_writer")

    assert "headline" in caplog.text
    assert "checkout is OOM-killing" in caplog.text
    assert '{"headline"' not in caplog.text


def test_every_part_of_a_turn_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _after(_Response([_Part("First thought."), _Part("Second thought.")]))

    assert "First thought." in caplog.text
    assert "Second thought." in caplog.text


def test_a_streamed_fragment_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """One turn reads as one line, not as one line per token."""
    with caplog.at_level(logging.INFO):
        _after(_Response([_Part("Satu")], partial=True))

    assert caplog.text == ""


def test_a_part_carrying_no_text_is_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A consultation is a part with no words in it, and is logged where it is made."""
    with caplog.at_level(logging.INFO):
        _after(_Response([_Part(None), _Part("")]))

    assert caplog.text == ""


def test_a_response_carrying_nothing_at_all_is_survived(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A model error reaches this seat with no content, and must not end the run."""
    with caplog.at_level(logging.INFO):
        _after(_Response(None))

    assert caplog.text == ""


def test_the_response_reaches_the_run_untouched() -> None:
    """Watching is all it does: returning a response would replace the model's."""
    assert _after(_Response([_Part("A hypothesis.")])) is None
