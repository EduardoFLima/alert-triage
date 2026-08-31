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
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from alert_triage.investigation.adapters.adk.normalisation import (
    Linker,
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

OnToolError = Callable[..., dict[str, Any] | None]
"""How ADK offers a tool's failure before it re-raises it.

A callback returning a record answers the call with it instead; returning
``None`` lets the failure propagate, which for an unhandled tool error means
ending the whole run.
"""

BeforeTool = Callable[..., dict[str, Any] | None]
"""How ADK offers a tool call for inspection before it is made.

A callback returning a record skips the call and uses that record as its
result, which is what lets a refusal be a refusal rather than a tally.
"""


class Links(Protocol):
    """How a platform addresses what a retrieval returned, at both grains.

    Injected rather than imported: this module is the framework's side of the
    boundary, and which route opens a log item is the platform adapter's
    knowledge. A deployment that supplies none gets evidence with no addresses,
    which is what evidence has always been here.

    The two grains are the two a citation has. ``to_retrieval`` addresses the
    search a retrieval came from, which is what a finding about an aggregate
    cites; ``to_item`` addresses one thing within it, which is what a finding
    about a pattern cites. Both answer with an address, never with evidence.
    """

    def to_retrieval(self, args: Mapping[str, Any]) -> str | None:
        """Where the search that produced this retrieval is opened."""
        ...

    def to_item(self, payload: Any, within: str | None) -> str | None:
        """Where this item is opened, or ``within`` when it names no item."""
        ...


class Retrieved:
    """What this investigation actually retrieved, keyed for citation.

    One instance per investigation. It is deliberately stateful and short
    lived: what may be cited is exactly what this investigation was shown, so
    a stale identifier from an earlier incident cannot resolve.
    """

    def __init__(self, link: Links | None = None) -> None:
        """Start with nothing retrieved, nothing citable, and nothing failed.

        Args:
            link: How this deployment's platform addresses what it returns.
                Absent, every piece of evidence is kept without an address.
        """
        self._evidence: dict[str, EvidenceItem] = {}
        self._retrievals = 0
        self._failures: list[str] = []
        self._link = link

    @property
    def retrievals(self) -> int:
        """How many retrievals came back with something."""
        return self._retrievals

    @property
    def failures(self) -> tuple[str, ...]:
        """Why each retrieval that failed did, in the order they failed."""
        return tuple(self._failures)

    def retain_evidence(
        self, result: Any, args: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Keep what a tool returned and describe it in the terms it may be cited in.

        Args:
            result: What the tool returned, as ADK handed it over.
            args: What the tool was called with. The query is in here, which is
                what a retrieval with no discrete items is addressed by.

        Returns:
            The call and its items under the identifiers that resolve, which is
            what the model is given in place of the result itself.
        """
        self._retrievals += 1
        call = f"{_CALL_PREFIX}{self._retrievals}"
        address = self._address_of(args or {})
        items = items_from(result, call, self._item_addresses(address))
        self._evidence[call] = EvidenceItem(
            id=call,
            instant=None,
            summary=summarise(readable(result)),
            payload=result,
            url=address,
        )
        for item in items:
            self._evidence[item.id] = item
        return self._offered(call, items, result)

    def refuse_evidence(self, reason: str) -> dict[str, Any]:
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

    def _address_of(self, args: Mapping[str, Any]) -> str | None:
        """Where the search this retrieval came from is opened."""
        return None if self._link is None else self._link.to_retrieval(args)

    def _item_addresses(self, within: str | None) -> Linker | None:
        """How each item of this retrieval is addressed, given where it came from."""
        link = self._link
        if link is None:
            return None
        return lambda payload: link.to_item(payload, within)

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


def keep_evidence_callback(
    retrieved: Retrieved, permitted: frozenset[str]
) -> AfterTool:
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
        name = named_tool(tool)
        if name not in permitted:
            return None
        failure = _failure_in(tool_response)
        if failure is not None:
            return retrieved.refuse_evidence(f"{name} failed: {failure}")
        return retrieved.retain_evidence(tool_response, args)

    return _kept


def log_tool_call() -> BeforeTool:
    """The callback that watches a tool call on its way out, and permits it.

    It enforces nothing today. It exists because the per-agent tool-call bound
    belongs exactly here, and a seat with a test already on it is what makes
    that a body to write rather than a boundary to find.

    Returns:
        The ``before_tool_callback`` to register on a specialist.
    """

    def _logged(*, tool: Any, args: dict[str, Any], tool_context: Any) -> None:
        _log.info("A specialist is calling %s with %r", named_tool(tool), args)
        return None

    return _logged


def _failure_in(result: Any) -> str | None:
    """Why this result is a failed retrieval, or ``None`` if it is not one.

    Three shapes, and each is a failure the model must not read as an answer:
    the server refused the call, ADK converted an exception into a result, or
    what came back carries nothing that can be read at all.

    The last of those is checked after an empty answer has been let through,
    because "there are none" and "this could not be read" are different facts
    and only the second is a failure.
    """
    if isinstance(result, dict):
        if result.get("isError"):
            return _detail(result) or "the platform refused the call"
        error = result.get("error")
        if error is not None:
            return str(error)
        if _answered_with_nothing(result):
            return None
    if readable(result) is None:
        return "the platform's answer carried nothing that could be read"
    return None


def _answered_with_nothing(result: dict[str, Any]) -> bool:
    """Whether the platform answered this call, and the answer was empty.

    A signal a deployment does not have — no container workload, no
    instrumented traces, no host metrics for a managed service — comes back
    as an answer with nothing in it. Recording that as a failure would mark
    every investigation on such a deployment incomplete, which is the
    incompleteness marker losing its meaning for the deployments most likely
    to need it.

    An empty answer is distinguishable from an unreadable one by its shape:
    the server either gave structure that happens to be empty, or explicitly
    returned no content at all. A result carrying content that reads as
    nothing is neither, and stays a failure.
    """
    structured = result.get("structuredContent")
    if isinstance(structured, dict | list):
        return not structured
    content = result.get("content")
    return isinstance(content, list) and not content


def _detail(result: dict[str, Any]) -> str:
    """What a refused call said about itself, for whoever tunes the investigation."""
    said = readable(result)
    return "" if said is None else summarise(said)


def named_tool(tool: Any) -> str:
    """What to call the tool in a log line or a failure record.

    Shared with the consultation callbacks, which sit on the same seat for a
    manager whose tools are its specialists and need the same answer.
    """
    return str(getattr(tool, "name", tool))
