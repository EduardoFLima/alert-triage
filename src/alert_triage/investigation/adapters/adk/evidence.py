"""Standing between a tool result and the model that is about to read it.

The model is never given the chance to write evidence. Every tool result passes
through ``Retrieved`` on its way to the model, which keeps it and hands back a
citable form in its place: the retrieval under ``call-N``, and each discrete
item within it under ``call-N/item-M``. What the model may cite is therefore
exactly what it was shown. A finding about a pattern cites items; a finding
about an aggregate — a flame graph, a dependency map — cites the call it came
from, because there are no items in it to point at.

A failed retrieval is never retained, because it evidences nothing. It is
recorded, and replaced with the refusal the discipline states, so that nothing
can be concluded from it in either direction.

Which citations then survive into findings is the discipline's own business,
in ``investigation/domain/evidence.py``.
"""

import logging
from collections.abc import Callable, Sequence
from typing import Any

from alert_triage.investigation.adapters.adk.normalisation import (
    items_from,
    readable,
    summarise,
)
from alert_triage.investigation.contract import EvidenceItem
from alert_triage.investigation.domain.evidence import RETRIEVAL_FAILED

_log = logging.getLogger(__name__)

_CALL_PREFIX = "call-"

AfterTool = Callable[..., dict[str, Any] | None]
"""How ADK hands a tool result over before the model sees it.

Loosely typed on purpose: the framework passes its own tool and context
objects, and this project reads a name off the first and nothing off the
second, so a unit test drives the callback with no framework at all.
"""

BeforeTool = Callable[..., None]
"""How ADK offers a tool call for inspection before it is made."""


class Retrieved:
    """What this investigation actually retrieved, keyed for citation.

    One instance per investigation. It is deliberately stateful and short
    lived: what may be cited is exactly what this investigation was shown, so
    a stale identifier from an earlier incident cannot resolve.
    """

    def __init__(self) -> None:
        """Start with nothing retrieved, nothing citable, and nothing failed."""
        self._evidence: dict[str, EvidenceItem] = {}
        self._retrievals = 0
        self._failures: list[str] = []

    @property
    def retrievals(self) -> int:
        """How many retrievals came back with something."""
        return self._retrievals

    @property
    def failures(self) -> tuple[str, ...]:
        """Why each retrieval that failed did, in the order they failed."""
        return tuple(self._failures)

    def retain(self, result: Any) -> dict[str, Any]:
        """Keep what a tool returned and describe it in the terms it may be cited in.

        Args:
            result: What the tool returned, as ADK handed it over.

        Returns:
            The call and its items under the identifiers that resolve, which is
            what the model is given in place of the result itself.
        """
        self._retrievals += 1
        call = f"{_CALL_PREFIX}{self._retrievals}"
        items = items_from(result, call)
        self._evidence[call] = EvidenceItem(
            id=call,
            instant=None,
            summary=summarise(readable(result)),
            payload=result,
        )
        for item in items:
            self._evidence[item.id] = item
        return self._offered(call, items, result)

    def refuse(self, reason: str) -> dict[str, Any]:
        """Record a failed retrieval and answer it in terms nothing can misread.

        Args:
            reason: What went wrong, for whoever tunes the investigation.

        Returns:
            The refusal the model is given in place of the failure.
        """
        self._failures.append(reason)
        _log.warning("A retrieval failed and was refused to the model: %s", reason)
        return {
            "retrieval_failed": True,
            "detail": reason,
            "read_this_as": RETRIEVAL_FAILED,
        }

    def resolve(self, citation: str) -> EvidenceItem | None:
        """The evidence behind a citation, or ``None`` if there is none."""
        return self._evidence.get(citation)

    def _offered(
        self, call: str, items: Sequence[EvidenceItem], result: Any
    ) -> dict[str, Any]:
        """Present one retrieval as what it is and what may be cited from it."""
        offered: dict[str, Any] = {
            "call": call,
            "items": [
                {
                    "id": item.id,
                    "instant": item.instant.isoformat() if item.instant else None,
                    "summary": item.summary,
                    "data": item.payload,
                }
                for item in items
            ],
        }
        if not items:
            offered["summary"] = self._evidence[call].summary
            offered["data"] = readable(result)
            offered["cite_as"] = call
        return offered


def evidence_kept(retrieved: Retrieved, permitted: frozenset[str]) -> AfterTool:
    """The callback that stands between a tool result and the model reading it.

    Registered on every specialist, closing over one investigation's
    ``Retrieved``. A closure rather than a framework plugin: a plugin is global
    to the runner and would have to find its way back to the right
    investigation, while a closure already holds it, which is what scopes
    citations to this incident.

    It covers tools nobody wrote a method for, which is the point: every result
    from the platform is checked, whether or not this project has ever heard of
    the tool that produced it.

    Only from the platform, though. A framework passes its own tools through
    the same callback — the one it uses to collect a structured answer, among
    others — and their results are not evidence, are not citable, and cannot
    fail a retrieval that was never made. What a specialist declared is the
    line, which is the same line everything else in this slice draws.

    Args:
        retrieved: What this investigation has gathered so far.
        permitted: The tools this specialist declared. A result from anything
            else passes through untouched.

    Returns:
        The ``after_tool_callback`` to register on a specialist.
    """

    def _kept(
        *, tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any
    ) -> dict[str, Any] | None:
        name = _named(tool)
        if name not in permitted:
            return None
        failure = _failure_in(tool_response)
        if failure is not None:
            return retrieved.refuse(f"{name} failed: {failure}")
        return retrieved.retain(tool_response)

    return _kept


def calls_logged() -> BeforeTool:
    """The callback that watches a tool call on its way out, and permits it.

    It enforces nothing today. It exists because the per-agent tool-call bound
    belongs exactly here, and a seat with a test already on it is what makes
    that a body to write rather than a boundary to find.

    Returns:
        The ``before_tool_callback`` to register on a specialist.
    """

    def _logged(*, tool: Any, args: dict[str, Any], tool_context: Any) -> None:
        _log.info("A specialist is calling %s with %r", _named(tool), args)
        return None

    return _logged


def _failure_in(result: Any) -> str | None:
    """Why this result is a failed retrieval, or ``None`` if it is not one.

    Three shapes, and each is a failure the model must not read as an answer:
    the server refused the call, ADK converted an exception into a result, or
    what came back carries nothing that can be read at all.
    """
    if isinstance(result, dict):
        if result.get("isError"):
            return _detail(result) or "the platform refused the call"
        error = result.get("error")
        if error is not None:
            return str(error)
    if readable(result) is None:
        return "the platform's answer carried nothing that could be read"
    return None


def _detail(result: dict[str, Any]) -> str:
    """What a refused call said about itself, for whoever tunes the investigation."""
    said = readable(result)
    return "" if said is None else summarise(said)


def _named(tool: Any) -> str:
    """What to call the tool in a log line or a failure record."""
    return str(getattr(tool, "name", tool))
