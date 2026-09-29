"""Evidence is read shallowly because tool schemas are discovered at runtime.

Unknown result shapes degrade to call-level evidence rather than errors.
"""

import json
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from alert_triage.investigation.contract import EvidenceItem

ENVELOPE_KEYS = ("logs", "data", "results", "result")
"""Widening this makes a new tool citable item by item instead of whole."""

SUMMARY_KEYS = ("message", "text", "title", "name", "summary")

INSTANT_KEYS = ("timestamp", "time", "date", "started_at", "occurred_at")

Linker = Callable[[Any], str | None]
"""Injected so item URLs remain platform adapter knowledge."""

MAX_SUMMARY_CHARS = 300
"""Enough for a phone alert; the payload still carries the full item."""


def items_from(
    result: Any, call: str, link: Linker | None = None
) -> tuple[EvidenceItem, ...]:
    return tuple(
        _item(f"{call}/item-{position}", payload, link)
        for position, payload in enumerate(_items(readable(result)), start=1)
    )


def readable(result: Any) -> Any:
    """MCP answers may be structured or JSON text; evidence rules need not care."""
    if not isinstance(result, dict):
        return result
    structured = result.get("structuredContent")
    if isinstance(structured, dict | list):
        return structured
    if "content" not in result:
        return result
    return _parsed(_text_of(result))


def summarise(payload: Any) -> str:
    return _shortened(_line(payload))


def instant_of(payload: Any) -> datetime | None:
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


def _item(identifier: str, payload: Any, link: Linker | None) -> EvidenceItem:
    return EvidenceItem(
        id=identifier,
        instant=instant_of(payload),
        summary=summarise(payload),
        payload=payload,
        url=None if link is None else link(payload),
    )


def _items(payload: Any) -> Sequence[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ENVELOPE_KEYS:
            found = payload.get(key)
            if isinstance(found, list):
                return found
    return ()


def _line(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in SUMMARY_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return _rendered(payload)


def _rendered(payload: Any) -> str:
    try:
        return json.dumps(payload, default=str)
    except (TypeError, ValueError):
        return repr(payload)


def _shortened(line: str) -> str:
    """Cut on a word boundary so truncated links do not look followable.

    The full payload stays with the evidence item.
    """
    collapsed = " ".join(line.split())
    if len(collapsed) <= MAX_SUMMARY_CHARS:
        return collapsed
    kept = collapsed[:MAX_SUMMARY_CHARS]
    if not collapsed[MAX_SUMMARY_CHARS].isspace():
        kept = kept.rpartition(" ")[0] or kept
    return f"{kept.rstrip()} …"


def _parsed(text: str) -> Any:
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _text_of(result: dict[str, Any]) -> str:
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        block.get("text", "") or "" for block in content if isinstance(block, dict)
    )
