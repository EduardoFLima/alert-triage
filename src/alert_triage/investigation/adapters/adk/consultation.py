"""What the manager asked, and what came back checked.

The manager reaches each specialist as a tool, which puts a specialist's report
on the same seat as any other tool result: ``after_tool_callback``, before the
model reads it. Collecting findings there rather than out of the manager's own
answer is what keeps a model from standing between a checked finding and the
report — the manager reasons over its specialists' reports, it does not relay
them.

``Consulted`` is to consultation what ``Retrieved`` is to evidence, and the two
are deliberately separate: one guards fabrication, the other records what an
incident was asked and what it cost. One instance per investigation, so what a
report may claim about its own scope is a record of what ran.
"""

import json
import logging
from collections.abc import Sequence
from typing import Any

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

_log = logging.getLogger(__name__)

MAX_CONSULTATIONS = 8
"""How many questions one incident may cost.

What the vision's ``max_tool_calls_per_agent`` means for a manager whose tools
are its specialists. Stated here rather than configured, exactly as the MCP
timeouts are: stating a bound is this slice's work and tuning it is slice 12's.

It counts questions, not specialists, because bounding each specialist to one
consultation would forbid the manager's best move rather than bound it — reading
an answer and going back for the detail it now knows to ask for. Eight leaves
the four declared specialists reachable with four questions to spare, and a
budget that admitted each specialist exactly once would be a once-each rule
wearing a number.
"""

CONSULTATION_REFUSED = (
    "This consultation did not happen. The investigation has spent the questions "
    "it is allowed, so the specialist was not asked and has reported nothing. "
    "This is not a specialist that found nothing, and nothing about that signal "
    "may be concluded from it in either direction. Conclude from the "
    "consultations that did happen."
)
"""What a manager is handed in place of a consultation it may not make.

Deliberately verbose, for the reason ``RETRIEVAL_FAILED`` is: the one thing that
must not happen is a model reading a refusal as a specialist that came back
empty, and a terse error is exactly what invites that reading.
"""

CONSULTATION_FAILED = (
    "This consultation did not answer. The specialist was asked and something "
    "went wrong before it could report — it has told you nothing, and that is "
    "not the same as telling you there was nothing to find. Conclude nothing "
    "about that signal in either direction. Consult a different specialist, or "
    "ask this one again."
)
"""What a manager is handed when a consultation fails outright.

A specialist answering in prose where its schema was asked for raises inside the
framework, and an unhandled tool error ends the whole investigation — one
specialist's bad turn costing every other specialist's work. Answering the
manager instead keeps the failure where it belongs, on the one consultation that
had it.

Worded like the refusal above and for the same reason: a model reading "that
call failed" as "that signal is clean" is the misreading this whole context is
built to prevent.
"""


class Consulted:
    """Which specialists an investigation asked, and what survived their answers.

    One instance per investigation. It knows the whole crew because the crew is
    what the manager was offered, and a report's honesty about its own scope
    depends on the difference between that and what was actually asked.
    """

    def __init__(self, *, offered: Sequence[Specialist], retrieved: Retrieved) -> None:
        """Start with the crew offered and nothing yet asked.

        Args:
            offered: Every specialist the manager may reach.
            retrieved: This investigation's evidence, which every finding
                collected here is checked against.
        """
        self._offered = tuple(offered)
        self._retrieved = retrieved
        self._order: list[str] = []
        self._findings: list[Finding] = []
        self._refusals: list[str] = []

    @property
    def offered(self) -> tuple[Specialist, ...]:
        """Every specialist the manager was given to choose from."""
        return self._offered

    @property
    def order(self) -> tuple[str, ...]:
        """Which specialists were consulted, in the order they were asked.

        A specialist asked twice appears twice: this is what the investigation
        cost, not which signals it covered.
        """
        return tuple(self._order)

    @property
    def signals(self) -> tuple[Signal, ...]:
        """The signals actually consulted, each named once, in the order asked.

        What a report may claim it examined. A specialist declared and never
        asked is absent, which is the whole point: a signal nobody looked at
        must never read as a signal that was clean.
        """
        by_name = {specialist.name: specialist.signal for specialist in self._offered}
        seen: list[Signal] = []
        for name in self._order:
            signal = by_name.get(name)
            if signal is not None and signal not in seen:
                seen.append(signal)
        return tuple(seen)

    @property
    def findings(self) -> tuple[Finding, ...]:
        """Everything the specialists reported that its evidence bears out."""
        return tuple(self._findings)

    @property
    def refusals(self) -> tuple[str, ...]:
        """Which consultations were refused, and why, in the order they were asked.

        An investigation with any of these wanted to ask more and could not,
        which a reader has to be told: it is an account cut short rather than
        one the manager chose to stop.
        """
        return tuple(self._refusals)

    @property
    def exhausted(self) -> bool:
        """Whether this investigation has spent the questions it is allowed."""
        return len(self._order) >= MAX_CONSULTATIONS

    def fail(self, name: str, error: Exception) -> dict[str, Any]:
        """Record a consultation that could not answer, and say so unmistakably.

        Args:
            name: The specialist that was asked and could not report.
            error: What went wrong, for whoever tunes the investigation.

        Returns:
            The answer the manager is given in place of the report.
        """
        reason = f"the {name} was consulted and could not answer: {error}"
        self._refusals.append(reason)
        _log.warning("A consultation failed: %s", reason)
        return {
            "consultation_failed": True,
            "detail": reason,
            "read_this_as": CONSULTATION_FAILED,
        }

    def refuse(self, name: str) -> dict[str, Any]:
        """Record a consultation that may not be made, and answer it unmistakably.

        Args:
            name: The specialist that was asked for and not run.

        Returns:
            The refusal the manager is given in place of running it.
        """
        reason = (
            f"the {name} was not consulted: this investigation has spent its "
            f"{MAX_CONSULTATIONS} questions"
        )
        self._refusals.append(reason)
        _log.warning("A consultation was refused: %s", reason)
        return {
            "consultation_refused": True,
            "detail": reason,
            "read_this_as": CONSULTATION_REFUSED,
        }

    def named(self, name: str) -> Specialist | None:
        """The specialist a tool name refers to, or ``None`` for anything else."""
        for specialist in self._offered:
            if specialist.name == name:
                return specialist
        return None

    def record(self, specialist: Specialist, reported: Any) -> None:
        """Note that a specialist was asked, and keep what its answer bears out.

        Being asked and answering legibly are different facts, and the first is
        recorded whatever the second turns out to be: a specialist whose report
        could not be read was still consulted, and a report claiming its signal
        was never examined would be as wrong as one claiming it was clean.

        Args:
            specialist: The specialist that was consulted.
            reported: What it reported, however the framework handed it over.
        """
        self._order.append(specialist.name)
        self._findings.extend(
            findings_from(
                reported_findings(reported), self._retrieved, specialist.signal
            ).findings
        )


def reported_findings(reported: Any) -> list[Any]:
    """Read the findings out of what a specialist reported, however little that is.

    A specialist's structured answer crosses the framework on its way here and
    may arrive as the record it declared, as that record wrapped in a result
    field, or as the JSON text of one. All three are the same answer, and none
    of them is worth failing an investigation over: a report nothing can be read
    out of contributes no findings, which the evidence check would have arrived
    at anyway.
    """
    payload = _unwrapped(reported)
    if not isinstance(payload, dict):
        _log.warning("A specialist reported something unreadable: %r", reported)
        return []
    findings = payload.get("findings")
    return findings if isinstance(findings, list) else []


def _unwrapped(reported: Any) -> Any:
    """What a specialist reported, whatever the framework wrapped it in."""
    if isinstance(reported, str):
        return _parsed(reported)
    if isinstance(reported, dict) and "findings" not in reported:
        held = reported.get("result", reported.get("response"))
        if held is not None:
            return _unwrapped(held)
    return reported


def _parsed(text: str) -> Any:
    """The record a piece of text carries, or the text itself if it carries none."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def collect_findings_callback(consulted: Consulted) -> AfterTool:
    """The callback that keeps what a specialist reported before the manager reads it.

    Registered on the manager, whose only tools are its specialists. It collects
    and hands the report on untouched: the manager needs what came back in order
    to choose what to ask next, and what reaches the report is what this checked.

    Args:
        consulted: This investigation's record of what was asked.

    Returns:
        The ``after_tool_callback`` to register on the manager.
    """

    def _collected(
        *, tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any
    ) -> dict[str, Any] | None:
        specialist = consulted.named(named_tool(tool))
        if specialist is None:
            return None
        _log.info("The %s reported back", specialist.name)
        consulted.record(specialist, tool_response)
        return None

    return _collected


def bound_consultations_callback(consulted: Consulted) -> BeforeTool:
    """The callback that decides whether one more question may be asked.

    It refuses rather than counts. The seat matters: a callback can decline the
    call, whereas a coordinator tallying afterwards has already paid for the
    reasoning it wanted to prevent. It is the same seat slice 12's configurable
    bound belongs on, for the same reason.

    Args:
        consulted: This investigation's record of what has been asked.

    Returns:
        The ``before_tool_callback`` to register on the manager.
    """

    def _bounded(
        *, tool: Any, args: dict[str, Any], tool_context: Any
    ) -> dict[str, Any] | None:
        name = named_tool(tool)
        specialist = consulted.named(name)
        if specialist is None:
            return None
        if consulted.exhausted:
            return consulted.refuse(name)
        _log.info("Consulting the %s: %r", name, args)
        return None

    return _bounded


def failed_consultation_callback(consulted: Consulted) -> OnToolError:
    """The callback that keeps a specialist's failure to that specialist.

    Without one, the framework re-raises: a single specialist answering in prose
    where its schema was asked for ends the whole investigation, and every other
    specialist's work goes with it. That is the wrong blast radius — a
    consultation that could not answer is exactly the case the manager is
    equipped to route around, so it is told, and it decides.

    Only a specialist's failure is answered. Anything else — a framework tool,
    the one that collects the structured answer — is left to raise, because a
    failure there is not a consultation that went wrong and swallowing it would
    hide a real fault.

    Args:
        consulted: This investigation's record of what was asked.

    Returns:
        The ``on_tool_error_callback`` to register on the manager.
    """

    def _failed(
        *, tool: Any, args: dict[str, Any], tool_context: Any, error: Exception
    ) -> dict[str, Any] | None:
        name = named_tool(tool)
        if consulted.named(name) is None:
            return None
        return consulted.fail(name, error)

    return _failed
