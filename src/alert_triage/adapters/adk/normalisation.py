"""Reading discrete evidence out of whatever a tool happened to return.

Deliberately shallow, and that is the whole design. A specialist discovers its
tools at runtime, so there is no catalogue to write a reader against: what is
knowable without per-tool knowledge is that a result is either a list of
things, a list of things inside an envelope, or one thing. The first two yield
items; the third yields none, and a tool nobody anticipated degrades to a
result citable as a whole rather than to an error.

Each item is normalised only as far as rendering it demands — an instant where
the payload offers one and a line a human can read — and the payload travels
along untouched for anyone who wants the rest of it. That is the trade this
project makes once, here, instead of fifteen times, one per tool.
"""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from alert_triage.domain.findings import EvidenceItem

ENVELOPE_KEYS = ("logs", "data", "results")
"""Keys a platform is known to wrap its entries in.

Widening this list is how a newly reached tool's entries become citable one by
one; a result whose envelope is not here is still citable whole, so the cost of
an omission is coarser evidence rather than a failure.
"""

SUMMARY_KEYS = ("message", "text", "title", "name", "summary")
"""Where a human-readable line is usually found in an entry."""

INSTANT_KEYS = ("timestamp", "time", "date", "started_at", "occurred_at")
"""Where the instant an entry concerns is usually found."""

MAX_SUMMARY_CHARS = 300
"""How much of an entry a summary shows before it stops being a line.

A report is read by a human on a phone at three in the morning; the payload is
what is there for the reader who wants everything.
"""


def items_from(result: Any, call: str) -> tuple[EvidenceItem, ...]:
    """The discrete items within one tool result, in the order they arrived.

    Args:
        result: What the tool returned, as ADK handed it over.
        call: The identifier this retrieval is cited by. Items are addressed
            within it, so a citation names both the call and the item.

    Returns:
        One item per entry found, or nothing at all when the result has no
        discrete entries to speak of.
    """
    return tuple(
        _item(f"{call}/item-{position}", payload)
        for position, payload in enumerate(_entries(readable(result)), start=1)
    )


def readable(result: Any) -> Any:
    """What a tool result says, with the protocol's wrapping taken off.

    A server may answer structurally or as a block of JSON text. Both are read
    here, so the shape of an MCP answer stays this module's problem rather than
    the evidence rules' or the report's.
    """
    if not isinstance(result, dict):
        return result
    structured = result.get("structuredContent")
    if isinstance(structured, dict | list):
        return structured
    if "content" not in result:
        return result
    return _parsed(_text_of(result))


def summarise(payload: Any) -> str:
    """The line a human reads to recognise this payload."""
    return _shortened(_line(payload))


def instant_of(payload: Any) -> datetime | None:
    """When the payload says it happened, or ``None`` where it does not say."""
    if not isinstance(payload, dict):
        return None
    for key in INSTANT_KEYS:
        raw = payload.get(key)
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                continue
    return None


def _item(identifier: str, payload: Any) -> EvidenceItem:
    """Normalise one entry as far as reading it demands, and no further."""
    return EvidenceItem(
        id=identifier,
        instant=instant_of(payload),
        summary=summarise(payload),
        payload=payload,
    )


def _entries(payload: Any) -> Sequence[Any]:
    """The entries within a result, where it has any."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ENVELOPE_KEYS:
            found = payload.get(key)
            if isinstance(found, list):
                return found
    return ()


def _line(payload: Any) -> str:
    """Find something worth reading in a payload, however it is shaped."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in SUMMARY_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return _rendered(payload)


def _rendered(payload: Any) -> str:
    """Render a payload with no line of its own into one."""
    try:
        return json.dumps(payload, default=str)
    except (TypeError, ValueError):
        return repr(payload)


def _shortened(line: str) -> str:
    """Keep a summary to the length of something a human reads."""
    collapsed = " ".join(line.split())
    if len(collapsed) <= MAX_SUMMARY_CHARS:
        return collapsed
    return collapsed[:MAX_SUMMARY_CHARS] + "…"


def _parsed(text: str) -> Any:
    """Read a block of text as JSON, or leave it as the text it is."""
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _text_of(result: dict[str, Any]) -> str:
    """Join whatever text a tool result carries."""
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        block.get("text", "") or "" for block in content if isinstance(block, dict)
    )
