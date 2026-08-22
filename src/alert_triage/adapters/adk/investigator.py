"""The Investigator implemented as a crew of specialist agents — today, one.

Slice 7 adds the APM, Trace, and Infrastructure specialists behind this same
method and concatenates their findings; the port, the run, and the report do
not change, and each finding names its signal so a multi-specialist result
stays legible without changing shape.

Two boundaries are drawn here and nowhere else. The tool the agent is given is
the ``ObservabilityPlatform`` port wrapped so ADK can call it, which is what
keeps the agent free of any platform's tool names. And every record that tool
returns is registered with ``Retrieved`` on the way past, which is what makes
the agent's citations checkable and its fabrications inert.

How the agent is actually driven is injected rather than hard-wired, so
everything either side of the model call — the tool, the translation, the
failure handling — is exercised by unit tests with no model and no network.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from alert_triage.adapters.adk.evidence import Retrieved, findings_from
from alert_triage.adapters.adk.logs_agent import describe
from alert_triage.domain.findings import Findings
from alert_triage.domain.incident import Incident
from alert_triage.domain.window import Window
from alert_triage.ports.investigator import InvestigatorError
from alert_triage.ports.observability_platform import (
    ObservabilityPlatform,
    ObservabilityPlatformError,
)

if TYPE_CHECKING:
    from google.adk.models import BaseLlm

_log = logging.getLogger(__name__)

RunAgent = Callable[[Any, str], dict[str, Any]]
"""How the agent is driven: given its tool and its prompt, report what it found.

An argument rather than a detail so that a test can stand in for the model. The
production implementation builds the ADK agent and runs it; both return the
same payload shape, which is what ``findings_from`` checks.
"""


class AdkInvestigator:
    """An investigation run by an agent crew, behind the ``Investigator`` port."""

    def __init__(self, *, platform: ObservabilityPlatform, run_agent: RunAgent) -> None:
        """Build an investigator over one platform and one way of running agents.

        Args:
            platform: Where evidence is gathered from.
            run_agent: How the agent is driven for one incident.
        """
        self._platform = platform
        self._run_agent = run_agent

    def investigate(self, incident: Incident) -> Findings:
        """Investigate one incident and report what was found.

        A fresh ``Retrieved`` per call is what scopes citations to this
        investigation: an identifier the model remembers from another incident
        resolves to nothing and its finding is dropped.

        Args:
            incident: The incident to investigate.

        Returns:
            The findings whose evidence the platform actually returned.

        Raises:
            InvestigatorError: The investigation could not be completed.
        """
        retrieved = Retrieved()
        try:
            reported = self._run_agent(
                self._tool(incident, retrieved), describe(incident)
            )
        except ObservabilityPlatformError as error:
            raise InvestigatorError(
                f"Evidence could not be gathered for {incident.service}: {error}"
            ) from error
        except Exception as error:
            raise InvestigatorError(
                f"Investigating {incident.service} failed: {error}"
            ) from error
        return findings_from(_reported_findings(reported), retrieved)

    def _tool(self, incident: Incident, retrieved: Retrieved) -> Any:
        """The log search, bound to this incident's investigation.

        Named and annotated for the model's benefit: ADK derives the tool's
        schema from this signature, so it takes the plain strings a model can
        produce rather than a domain value it has never heard of.
        """

        def search_logs(
            service: str, start: str, end: str, query: str
        ) -> list[dict[str, Any]]:
            """Search a service's logs over a window.

            Args:
                service: The service whose logs to search.
                start: Start of the window, ISO-8601.
                end: End of the window, ISO-8601.
                query: What to look for, in plain terms.

            Returns:
                The matching records. Each carries an `id` to cite it by.
            """
            found = self._platform.search_logs(
                service, _window(start, end, incident), query
            )
            _log.info(
                "Searched %s logs for %r: %d record(s)", service, query, len(found)
            )
            return retrieved.offer(found)

        return search_logs


def _window(start: str, end: str, incident: Incident) -> Window:
    """Read the window the model asked about, falling back to the incident's.

    A model that garbles a timestamp gets the incident's own window rather than
    an error: the window it should have asked for is the one the alerts span,
    and that is knowable without it.
    """
    try:
        return Window(
            start=datetime.fromisoformat(start), end=datetime.fromisoformat(end)
        )
    except ValueError:
        _log.warning(
            "The agent asked about an unreadable window (%r to %r); using the "
            "incident's own",
            start,
            end,
        )
        return incident.window


def _reported_findings(reported: Any) -> list[Any]:
    """Read the findings out of what the agent reported, however little that is."""
    if not isinstance(reported, dict):
        return []
    findings = reported.get("findings")
    return findings if isinstance(findings, list) else []


def run_with_adk(model: "str | BaseLlm") -> RunAgent:
    """Drive the Logs agent with a real model, once per incident.

    ADK is asynchronous underneath; the event loop is owned here so that the
    port, the run, and the composition root all stay synchronous.

    The model arrives built, and already told how to authenticate: what it
    costs to reach is resolved from the run's environment in the composition
    root, not rediscovered here from the process's.

    Args:
        model: The model the agent reasons with.

    Returns:
        A callable that runs the agent for one incident and returns what it
        reported.
    """

    def _run(tool: Any, prompt: str) -> dict[str, Any]:
        from alert_triage.adapters.adk.logs_agent import build_logs_agent

        agent = build_logs_agent(model=model, search_logs=tool)
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
