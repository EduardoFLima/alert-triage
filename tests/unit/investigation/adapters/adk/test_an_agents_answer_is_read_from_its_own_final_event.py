import json
from typing import Any

from alert_triage.investigation.adapters.adk.investigator import answer_in


class _Part:
    def __init__(self, text: str | None = None) -> None:
        self.text = text


class _Content:
    def __init__(self, *parts: _Part) -> None:
        self.parts = list(parts)


class _Event:
    def __init__(
        self,
        author: str = "diagnostician",
        *,
        text: str | None = None,
        final: bool = True,
    ) -> None:
        self.author = author
        self.content = _Content(_Part(text)) if text is not None else _Content()
        self._final = final

    def is_final_response(self) -> bool:
        return self._final


def _concluded(hypothesis: str = "the pods are out of memory") -> str:
    return json.dumps({"hypothesis": hypothesis, "confidence": "high"})


def test_the_structured_answer_is_read_from_a_final_event() -> None:
    answer = answer_in([_Event(text=_concluded())], "diagnostician")

    assert answer == {"hypothesis": "the pods are out of memory", "confidence": "high"}


def test_a_final_event_carrying_no_text_does_not_erase_the_answer() -> None:
    events: list[Any] = [
        _Event(text=_concluded()),
        _Event(),
    ]

    assert (
        answer_in(events, "diagnostician")["hypothesis"] == "the pods are out of memory"
    )


def test_a_later_answer_replaces_an_earlier_one() -> None:
    events = [_Event(text=_concluded("first")), _Event(text=_concluded("second"))]

    assert answer_in(events, "diagnostician")["hypothesis"] == "second"


def test_an_answer_from_another_agent_is_not_read_as_this_ones() -> None:
    reported = json.dumps({"findings": [{"observation": "OOMKilled recurs"}]})
    events = [_Event("apm_specialist", text=reported)]

    assert answer_in(events, "diagnostician") == {}


def test_an_agent_that_never_answered_structurally_returns_nothing() -> None:
    events = [_Event(text="I could not work out what is going on.")]

    assert answer_in(events, "diagnostician") == {}


def test_an_event_that_is_not_final_is_not_an_answer() -> None:
    events = [_Event(text=_concluded(), final=False)]

    assert answer_in(events, "diagnostician") == {}


def test_a_non_record_answer_is_not_an_answer() -> None:
    events = [_Event(text=json.dumps(["not", "a", "record"]))]

    assert answer_in(events, "diagnostician") == {}
