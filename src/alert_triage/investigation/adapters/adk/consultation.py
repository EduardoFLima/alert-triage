"""Reports are collected before the manager can rewrite checked findings."""

import json
import logging
from collections.abc import Sequence
from typing import Any

from alert_triage.investigation.adapters.adk.bounds import Bounds
from alert_triage.investigation.adapters.adk.evidence import (
    AfterTool,
    BeforeTool,
    OnToolError,
    Retrieved,
    named_tool,
)
from alert_triage.investigation.contract import Finding, Signal
from alert_triage.investigation.domain.evidence import findings_from
from alert_triage.investigation.domain.specialist import Specialist
from alert_triage.shared import journal

_log = logging.getLogger(__name__)

CONSULTATION_REFUSED = (
    "This consultation did not happen. The investigation has spent the questions "
    "it is allowed, so the specialist was not asked and has reported nothing. "
    "This is not a specialist that found nothing, and nothing about that signal "
    "may be concluded from it in either direction. Conclude from the "
    "consultations that did happen."
)
"""Verbose so a refusal is not mistaken for a specialist that found nothing."""

CONSULTATION_FAILED = (
    "This consultation did not answer. The specialist was asked and something "
    "went wrong before it could report — it has told you nothing, and that is "
    "not the same as telling you there was nothing to find. Conclude nothing "
    "about that signal in either direction. Consult a different specialist, or "
    "ask this one again."
)
"""A specialist failure must not abort the crew or read as a clean signal."""


class Consulted:
    """One per investigation, to separate specialists offered from specialists asked."""

    def __init__(
        self,
        *,
        offered: Sequence[Specialist],
        retrieved: Retrieved,
        bounds: Bounds | None = None,
    ) -> None:
        self._offered = tuple(offered)
        self._retrieved = retrieved
        self._bounds = bounds or Bounds()
        self._order: list[str] = []
        self._findings: list[Finding] = []
        self._refusals: list[str] = []

    @property
    def bounds(self) -> Bounds:
        """Prompt and callback read one Bounds so budgets cannot diverge."""
        return self._bounds

    @property
    def offered(self) -> tuple[Specialist, ...]:
        return self._offered

    @property
    def order(self) -> tuple[str, ...]:
        """A specialist asked twice appears twice: this is cost, not coverage."""
        return tuple(self._order)

    @property
    def signals(self) -> tuple[Signal, ...]:
        """An unasked specialist must not read as a signal that was clean."""
        by_name = {specialist.name: specialist.signal for specialist in self._offered}
        seen: list[Signal] = []
        for name in self._order:
            signal = by_name.get(name)
            if signal is not None and signal not in seen:
                seen.append(signal)
        return tuple(seen)

    @property
    def findings(self) -> tuple[Finding, ...]:
        return tuple(self._findings)

    @property
    def refusals(self) -> tuple[str, ...]:
        """Refusals mark an account cut short, not one the manager chose to stop."""
        return tuple(self._refusals)

    def declined(self, name: str) -> dict[str, Any] | None:
        reason = self._bounds.decline_consultation(name, len(self._order))
        return None if reason is None else self._refuse(name, reason)

    def fail(self, name: str, error: Exception) -> dict[str, Any]:
        reason = f"the {name} was consulted and could not answer: {error}"
        self._refusals.append(reason)
        _log.warning(journal.event(f"{name} could not answer", detail=reason))
        return {
            "consultation_failed": True,
            "detail": reason,
            "read_this_as": CONSULTATION_FAILED,
        }

    def _refuse(self, name: str, reason: str) -> dict[str, Any]:
        self._refusals.append(reason)
        return {
            "consultation_refused": True,
            "detail": reason,
            "read_this_as": CONSULTATION_REFUSED,
        }

    def named(self, name: str) -> Specialist | None:
        for specialist in self._offered:
            if specialist.name == name:
                return specialist
        return None

    def record(self, specialist: Specialist, reported: Any) -> tuple[Finding, ...]:
        """Asked and answered are separate; record the ask even with no findings."""
        kept = findings_from(
            reported_findings(reported), self._retrieved, specialist.signal
        ).findings
        self._order.append(specialist.name)
        self._findings.extend(kept)
        return kept


def reported_findings(reported: Any) -> list[Any]:
    """ADK may hand back the schema, a wrapped schema, or JSON text.

    Unreadable reports contribute no findings rather than failing the investigation.
    """
    payload = _unwrapped(reported)
    if not isinstance(payload, dict):
        _log.warning(
            journal.event(
                "a specialist reported something unreadable",
                reported=journal.shortened(repr(reported)),
            )
        )
        return []
    findings = payload.get("findings")
    return findings if isinstance(findings, list) else []


def _unwrapped(reported: Any) -> Any:
    if isinstance(reported, str):
        return _parsed(reported)
    if isinstance(reported, dict) and "findings" not in reported:
        held = reported.get("result", reported.get("response"))
        if held is not None:
            return _unwrapped(held)
    return reported


def _parsed(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def collect_findings_callback(consulted: Consulted) -> AfterTool:
    """Collects a specialist report before the manager reads it."""

    def _collected(
        *, tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any
    ) -> dict[str, Any] | None:
        specialist = consulted.named(named_tool(tool))
        if specialist is None:
            return None
        _log.info(_reported(specialist, consulted.record(specialist, tool_response)))
        return None

    return _collected


def _reported(specialist: Specialist, findings: Sequence[Finding]) -> str:
    """No findings is logged explicitly, so silence is not read as no consultation."""
    if not findings:
        return journal.event(
            f"{specialist.name} reported",
            "Reported nothing that its evidence bore out.",
            signal=specialist.signal.value,
        )
    return journal.event(
        f"{specialist.name} reported",
        "\n\n".join(finding.observation for finding in findings),
        signal=specialist.signal.value,
        findings=(
            f"{len(findings)}, over "
            f"{sum(finding.occurrences for finding in findings)} occurrence(s)"
        ),
        evidence=", ".join(
            item.id for finding in findings for item in finding.examples
        ),
    )


def bound_consultations_callback(consulted: Consulted) -> BeforeTool:
    """Refuses before consultation; counting later has already spent reasoning."""

    def _bounded(
        *, tool: Any, args: dict[str, Any], tool_context: Any
    ) -> dict[str, Any] | None:
        name = named_tool(tool)
        specialist = consulted.named(name)
        if specialist is None:
            return None
        refused = consulted.declined(name)
        if refused is not None:
            return refused
        _log.info(
            journal.event(
                f"consulting {name}",
                **{label: journal.shortened(asked) for label, asked in args.items()},
            )
        )
        return None

    return _bounded


def failed_consultation_callback(consulted: Consulted) -> OnToolError:
    """Unhandled ADK tool errors abort the whole crew.

    Only specialist failures are answered here; framework-tool failures still raise.
    """

    def _failed(
        *, tool: Any, args: dict[str, Any], tool_context: Any, error: Exception
    ) -> dict[str, Any] | None:
        name = named_tool(tool)
        if consulted.named(name) is None:
            return None
        return consulted.fail(name, error)

    return _failed
