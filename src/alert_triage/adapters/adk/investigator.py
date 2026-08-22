"""The Investigator implemented as a crew of specialists — today, one.

The crew is a tuple of declarations and this module walks it. It learns no
tool name, no tool signature, and no query dialect: those belong to the
declaration, which is what makes adding a specialist an edit to one file that
this one never sees. Every finding names the signal its specialist reports
under, so several specialists' work stays legible without the result changing
shape.

Two boundaries are drawn here and nowhere else. Every specialist reaches the
platform through its own filtered MCP toolset, so what it may ask is what its
declaration named. And every result crosses ``Retrieved`` on the way back,
which is what makes citations checkable, fabrications inert, and — the
property this slice turns on — a failed retrieval impossible to read as a
service that had nothing to say.

Three outcomes, and only three. Some retrievals failed and findings were
produced: findings, marked incomplete. Every retrieval failed: a failure, so
the incident is retried on the next run rather than reported as clean. No
retrieval attempted: an ordinary result, because a model that chose not to
look did look and found nothing to ask about.

How a specialist is actually driven is injected rather than hard-wired, so
everything either side of the model call is exercised by unit tests with no
model and no network.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Any

from alert_triage.adapters.adk.evidence import Retrieved, findings_from
from alert_triage.adapters.adk.specialists import (
    Deployment,
    Specialist,
    build_agent,
    describe,
)
from alert_triage.domain.findings import Finding, Findings
from alert_triage.domain.incident import Incident
from alert_triage.ports.investigator import InvestigatorError

_log = logging.getLogger(__name__)

RunSpecialist = Callable[[Specialist, Retrieved, str], dict[str, Any]]
"""How a specialist is driven: given its declaration, this investigation's
evidence, and what to look into, report what it found.

An argument rather than a detail so that a test can stand in for the model. The
production implementation builds the agent from the declaration and runs it;
both return the same payload shape, which is what ``findings_from`` checks.
"""


class AdkInvestigator:
    """An investigation run by a crew of specialists, behind the port."""

    def __init__(
        self, *, crew: Sequence[Specialist], run_specialist: RunSpecialist
    ) -> None:
        """Build an investigator over one crew and one way of running a specialist.

        Args:
            crew: The specialists to run, in the order to run them.
            run_specialist: How one specialist is driven for one incident.
        """
        self._crew = tuple(crew)
        self._run_specialist = run_specialist

    def investigate(self, incident: Incident) -> Findings:
        """Investigate one incident and report what was found.

        A fresh ``Retrieved`` per call is what scopes citations to this
        investigation: an identifier the model remembers from another incident
        resolves to nothing and its finding is dropped.

        Args:
            incident: The incident to investigate.

        Returns:
            The findings whose evidence the platform actually returned, marked
            incomplete if part of the evidence could not be gathered.

        Raises:
            InvestigatorError: The investigation could not be completed —
                a specialist errored, or nothing could be retrieved at all.
        """
        retrieved = Retrieved()
        found = self._report(incident, retrieved)
        if retrieved.failures and not retrieved.retrievals:
            raise InvestigatorError(
                f"No evidence could be gathered for {incident.service}: "
                f"{'; '.join(retrieved.failures)}"
            )
        return Findings(findings=found, retrieval_failures=retrieved.failures)

    def _report(self, incident: Incident, retrieved: Retrieved) -> tuple[Finding, ...]:
        """Run every specialist over one incident and collect what checks out."""
        prompt = describe(incident)
        found: list[Finding] = []
        for specialist in self._crew:
            found.extend(self._from(specialist, incident, retrieved, prompt))
        return tuple(found)

    def _from(
        self,
        specialist: Specialist,
        incident: Incident,
        retrieved: Retrieved,
        prompt: str,
    ) -> tuple[Finding, ...]:
        """What one specialist reported, minus whatever it could not evidence."""
        try:
            reported = self._run_specialist(specialist, retrieved, prompt)
        except Exception as error:
            raise InvestigatorError(
                f"The {specialist.name} investigating {incident.service} "
                f"failed: {error}"
            ) from error
        return findings_from(
            _reported_findings(reported), retrieved, specialist.signal
        ).findings


def _reported_findings(reported: Any) -> list[Any]:
    """Read the findings out of what a specialist reported, however little that is."""
    if not isinstance(reported, dict):
        return []
    findings = reported.get("findings")
    return findings if isinstance(findings, list) else []


def run_with_adk(deployment: Deployment) -> RunSpecialist:
    """Drive a specialist with a real model against a real platform.

    ADK is asynchronous underneath; the event loop is owned here so that the
    port, the run, and the composition root all stay synchronous.

    Args:
        deployment: Where the platform is, how to authenticate, and what a
            specialist reasons on when it names no model of its own.

    Returns:
        A callable that runs one specialist for one incident and returns what
        it reported.
    """

    def _run(
        specialist: Specialist, retrieved: Retrieved, prompt: str
    ) -> dict[str, Any]:
        agent = build_agent(specialist, deployment, retrieved)
        _log.info("Running the %s", specialist.name)
        return asyncio.run(_reported(agent, prompt))

    return _run


async def _reported(agent: Any, prompt: str) -> dict[str, Any]:
    """Run the agent to completion and hand back its structured output."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=agent, app_name="alert-triage")
    session = await runner.session_service.create_session(
        app_name="alert-triage", user_id="alert-triage"
    )
    last: dict[str, Any] = {}
    async for event in runner.run_async(
        user_id="alert-triage",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if getattr(event, "is_final_response", None) and event.is_final_response():
            last = _payload(event)
    return last


def _payload(event: Any) -> dict[str, Any]:
    """Read the structured findings out of a final event, if it carries any."""
    content = getattr(event, "content", None)
    for part in getattr(content, "parts", None) or ():
        text = getattr(part, "text", None)
        if text:
            import json

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}
