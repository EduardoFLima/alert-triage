"""Log model turns because consultations cannot explain why an agent was asked."""

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

from alert_triage.shared import journal

_log = logging.getLogger(__name__)

AfterModel = Callable[..., None]
"""Loosely typed because tests replace ADK framework objects with fakes."""


def log_reasoning(agent: str) -> AfterModel:
    """Returns nothing so logging cannot alter the response ADK continues with."""

    def _reasoned(*, callback_context: Any, llm_response: Any) -> None:
        if getattr(llm_response, "partial", False):
            return None
        said = "\n\n".join(_spoken(llm_response))
        if said:
            _log.info(_written(agent, said))
        return None

    return _reasoned


def _written(agent: str, said: str) -> str:
    answered = _answered(said)
    if answered is None:
        return journal.event(f"{agent} reasoning", said)
    return journal.event(
        f"{agent} answered", **{field: str(value) for field, value in answered.items()}
    )


def _answered(said: str) -> dict[str, Any] | None:
    try:
        answered = json.loads(said)
    except json.JSONDecodeError:
        return None
    return answered if isinstance(answered, dict) and answered else None


def _spoken(llm_response: Any) -> Iterator[str]:
    content = getattr(llm_response, "content", None)
    for part in getattr(content, "parts", None) or ():
        text = getattr(part, "text", None)
        if text:
            yield text
