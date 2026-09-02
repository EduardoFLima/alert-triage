"""What an agent said on its way to deciding, kept where a human can read it.

The consultation record answers what was asked and what came back. It cannot
answer why one specialist was asked and not another, because that lives in the
manager's own words and those are spent the moment the next turn begins. This
watches the seat they pass through and writes them down.

Two agents reason in one investigation and both pass this seat, so what is
written down says which of them said it. A turn is written down once, whole:
the manager's thought is one thought, and one line per part of the response
would break it up for no reason a reader benefits from.

An agent's last turn is not prose at all — it is the schema it was asked to
answer in. That is read back out as the fields it declared, because a run whose
conclusion reaches the log as a wall of JSON is the thing this is here to fix.

It only ever watches. A callback here may replace the model's response, and one
that did would be putting words in an agent's mouth rather than recording them
— so this returns nothing, and a run reasons identically whether or not anyone
is reading the log.
"""

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

from alert_triage.shared import journal

_log = logging.getLogger(__name__)

AfterModel = Callable[..., None]
"""How ADK hands a model response over before the run continues on it.

Loosely typed for the reason the tool callbacks are: the framework passes its
own context and response objects, this reads text off the second and nothing
off the first, and a unit test drives it with no framework at all.
"""


def log_reasoning(agent: str) -> AfterModel:
    """The callback that writes down what one agent said this turn.

    Registered on the agents that reason rather than retrieve: the manager,
    whose thread between consultations nothing else keeps, and the writer,
    whose turn is the report taking shape. A specialist reports through a
    schema its findings are checked out of, so its words are already kept.

    Args:
        agent: Whose words these are, as a reader of the log knows it.

    Returns:
        The ``after_model_callback`` to register on that agent.
    """

    def _reasoned(*, callback_context: Any, llm_response: Any) -> None:
        if getattr(llm_response, "partial", False):
            return None
        said = "\n\n".join(_spoken(llm_response))
        if said:
            _log.info(_written(agent, said))
        return None

    return _reasoned


def _written(agent: str, said: str) -> str:
    """One turn, as prose where it is prose and as its fields where it is not."""
    answered = _answered(said)
    if answered is None:
        return journal.event(f"{agent} reasoning", said)
    return journal.event(
        f"{agent} answered", **{field: str(value) for field, value in answered.items()}
    )


def _answered(said: str) -> dict[str, Any] | None:
    """The record this turn answered with, or ``None`` where it spoke in prose."""
    try:
        answered = json.loads(said)
    except json.JSONDecodeError:
        return None
    return answered if isinstance(answered, dict) and answered else None


def _spoken(llm_response: Any) -> Iterator[str]:
    """Everything this response said in words, which may be nothing.

    A turn that only calls a specialist carries parts with no text in it, and a
    turn the model failed on carries no content at all. Both are silence here,
    and both are already recorded where they happen.
    """
    content = getattr(llm_response, "content", None)
    for part in getattr(content, "parts", None) or ():
        text = getattr(part, "text", None)
        if text:
            yield text
