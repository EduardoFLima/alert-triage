"""What the manager said on its way to deciding, kept where a human can read it.

The consultation record answers what was asked and what came back. It cannot
answer why one specialist was asked and not another, because that lives in the
manager's own words and those are spent the moment the next turn begins. This
watches the seat they pass through and writes them down.

It only ever watches. A callback here may replace the model's response, and one
that did would be putting words in the Diagnostician's mouth rather than
recording them — so this returns nothing, and a run reasons identically whether
or not anyone is reading the log.
"""

import logging
from collections.abc import Callable, Iterator
from typing import Any

_log = logging.getLogger(__name__)

AfterModel = Callable[..., None]
"""How ADK hands a model response over before the run continues on it.

Loosely typed for the reason the tool callbacks are: the framework passes its
own context and response objects, this reads text off the second and nothing
off the first, and a unit test drives it with no framework at all.
"""


def log_reasoning() -> AfterModel:
    """The callback that writes down what the manager said this turn.

    Registered on the manager alone. A specialist reports through a schema its
    findings are checked out of, so its words are already kept; the manager's
    reasoning over those reports is what nothing else retains.

    Returns:
        The ``after_model_callback`` to register on the manager.
    """

    def _reasoned(*, callback_context: Any, llm_response: Any) -> None:
        if getattr(llm_response, "partial", False):
            return None
        for said in _spoken(llm_response):
            _log.info("The diagnostician is reasoning: %s", said)
        return None

    return _reasoned


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
