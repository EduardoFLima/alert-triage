"""Retrieved mediates tool results so citations name exactly what the model saw."""

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from alert_triage.investigation.adapters.adk.bounds import CALL_DECLINED, Bounds
from alert_triage.investigation.adapters.adk.normalisation import (
    Linker,
    items_from,
    readable,
    summarise,
)
from alert_triage.investigation.contract import EvidenceItem, Section
from alert_triage.investigation.domain.evidence import RETRIEVAL_FAILED
from alert_triage.shared import journal
from alert_triage.shared.window import Window

_log = logging.getLogger(__name__)

TOOL_CALL_LOGGER = f"{__name__}.tool_calls"
"""Separate logger for specialist working, apart from the investigation account."""

_tool_log = logging.getLogger(TOOL_CALL_LOGGER)

_CALL_PREFIX = "call-"

AfterTool = Callable[..., dict[str, Any] | None]
"""Loosely typed because tests replace ADK framework objects with fakes."""

OnToolError = Callable[..., dict[str, Any] | None]
"""Returning a record answers the failed call; returning None lets ADK raise."""

BeforeTool = Callable[..., dict[str, Any] | None]
"""Returning a record skips the call and uses that record as the result."""


class Links(Protocol):
    """Injected so evidence stays platform-blind while URLs stay platform-owned."""

    def to_retrieval(
        self, tool: str, args: Mapping[str, Any], service: str, env: str | None
    ) -> str | None: ...

    def to_item(
        self,
        tool: str,
        payload: Any,
        within: str | None,
        service: str,
        env: str | None,
    ) -> str | None: ...

    def to_service(
        self,
        service: str,
        window: Window,
        section: Section | None,
        env: str | None,
    ) -> str | None: ...


class Retrieved:
    """One per investigation, so stale citation IDs cannot resolve across incidents."""

    def __init__(
        self, link: Links | None = None, service: str = "", env: str | None = None
    ) -> None:
        self._evidence: dict[str, EvidenceItem] = {}
        self._retrievals = 0
        self._failures: list[str] = []
        self._link = link
        self._service = service
        self._env = env

    @property
    def retrievals(self) -> int:
        return self._retrievals

    @property
    def failures(self) -> tuple[str, ...]:
        """Failed and declined retrievals both mean the account asked for more."""
        return tuple(self._failures)

    def retain_evidence(
        self, tool: str, result: Any, args: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        self._retrievals += 1
        call = f"{_CALL_PREFIX}{self._retrievals}"
        address = self._address_of(tool, args or {})
        items = items_from(result, call, self._item_addresses(tool, address))
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

    def refuse_call(self, reason: str) -> dict[str, Any]:
        """Declined calls sit beside failed retrievals to explain incompleteness."""
        self._failures.append(reason)
        return {
            "call_declined": True,
            "detail": reason,
            "read_this_as": CALL_DECLINED,
        }

    def refuse_evidence(self, reason: str) -> dict[str, Any]:
        self._failures.append(reason)
        _log.warning(journal.event("retrieval refused to the model", reason=reason))
        return {
            "retrieval_failed": True,
            "detail": reason,
            "read_this_as": RETRIEVAL_FAILED,
        }

    def resolve(self, citation: str) -> EvidenceItem | None:
        return self._evidence.get(citation)

    def _address_of(self, tool: str, args: Mapping[str, Any]) -> str | None:
        if self._link is None:
            return None
        return self._link.to_retrieval(tool, args, self._service, self._env)

    def _item_addresses(self, tool: str, within: str | None) -> Linker | None:
        link = self._link
        if link is None:
            return None
        return lambda payload: link.to_item(
            tool, payload, within, self._service, self._env
        )

    def _offered(
        self, call: str, items: Sequence[EvidenceItem], result: Any
    ) -> dict[str, Any]:
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
    retrieved: Retrieved, permitted: frozenset[str], caller: str
) -> AfterTool:
    """A closure scopes citations to one investigation.

    Only declared platform tools become evidence; ADK framework tools pass through.
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
        offered = retrieved.retain_evidence(name, tool_response, args)
        _tool_log.info(
            journal.event(
                f"{caller} ← {name}",
                call=offered["call"],
                items=len(offered["items"]) or "none, cited as a whole",
                answered=journal.shortened(tool_response),
            )
        )
        return offered

    return _kept


def log_tool_call(
    caller: str,
    permitted: frozenset[str],
    retrieved: Retrieved | None = None,
    bounds: Bounds | None = None,
) -> BeforeTool:
    """Only declared tools are bounded; ADK framework tools still return schemas."""
    kept = retrieved if retrieved is not None else Retrieved()
    within = bounds or Bounds()

    def _logged(
        *, tool: Any, args: dict[str, Any], tool_context: Any
    ) -> dict[str, Any] | None:
        if named_tool(tool) not in permitted:
            return None
        declined = within.decline_call(caller)
        if declined is not None:
            return kept.refuse_call(declined)
        _tool_log.info(
            journal.event(
                f"{caller} → {named_tool(tool)}",
                **{name: journal.shortened(asked) for name, asked in args.items()},
            )
        )
        return None

    return _logged


def _failure_in(result: Any) -> str | None:
    """Errors and unreadable answers are failures; empty structured answers are not.

    The distinction keeps missing telemetry from making every run look incomplete.
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
    """Empty structured content is valid for signals a deployment does not have."""
    structured = result.get("structuredContent")
    if isinstance(structured, dict | list):
        return not structured
    content = result.get("content")
    return isinstance(content, list) and not content


def _detail(result: dict[str, Any]) -> str:
    said = readable(result)
    return "" if said is None else summarise(said)


def named_tool(tool: Any) -> str:
    return str(getattr(tool, "name", tool))
