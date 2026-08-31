"""The Investigator implemented as a manager and the crew it may consult.

The crew is no longer walked. Every specialist is offered to a manager, which
consults the ones this incident needs and chooses each from what the last one
reported. The coordinator here learns no tool name, no tool signature, and no
query dialect — those belong to the declarations — and it learns no routing
either, which belongs to the manager.

Three boundaries are drawn here and nowhere else. Every specialist reaches the
platform through its own filtered MCP toolset, so what it may ask is what its
declaration named. Every tool result crosses ``Retrieved`` on the way back,
which is what makes citations checkable and a failed retrieval impossible to
read as a quiet service. And every specialist's report crosses ``Consulted``
before the manager reads it, so what reaches a report is what was checked rather
than what the manager remembered.

The outcomes are unchanged from the walk, plus one. Some retrievals failed and
findings were produced: findings, marked incomplete. Every retrieval failed: a
failure, so the caller retries rather than reporting a service as clean. No
retrieval attempted: an ordinary result. And now — no specialist consulted at
all: also an ordinary result, with no signal claimed and no hypothesis, because
a manager that chose not to ask is not a platform that could not be reached, and
failing would cost a team its alerts over a model's judgement.

How the manager and the wording are actually driven is injected rather than
hard-wired, so everything either side of the model calls is exercised by unit
tests with no model and no network.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Any

from alert_triage.investigation.adapters.adk.agent import (
    Deployment,
    build_manager,
)
from alert_triage.investigation.adapters.adk.consultation import Consulted
from alert_triage.investigation.adapters.adk.evidence import Links, Retrieved
from alert_triage.investigation.contract import (
    Confidence,
    Diagnosis,
    Findings,
    InvestigationTarget,
)
from alert_triage.investigation.domain import account
from alert_triage.investigation.domain.specialist import Specialist
from alert_triage.investigation.ports.investigator import InvestigatorError

_log = logging.getLogger(__name__)

RunDiagnostician = Callable[
    [Sequence[Specialist], Consulted, Retrieved, str], dict[str, Any]
]
"""How the manager is driven: offered a crew, it consults and concludes.

An argument rather than a detail so that a test can stand in for the model and
assert what the manager was offered against what it chose to consult. The
production implementation builds an agent whose tools are the crew; a test's
consults whichever specialists it names.
"""


class AdkInvestigator:
    """An investigation routed by a manager over a crew, behind the port."""

    def __init__(
        self,
        *,
        crew: Sequence[Specialist],
        run_diagnostician: RunDiagnostician,
        links: Links | None = None,
    ) -> None:
        """Build an investigator over one crew, one manager, and one writer.

        Args:
            crew: The specialists to offer, every one of them.
            run_diagnostician: How the manager is driven for one target.
            links: How this deployment's platform addresses what it returns.
                Absent, evidence is gathered and reported without addresses.
        """
        self._crew = tuple(crew)
        self._run_diagnostician = run_diagnostician
        self._links = links

    def investigate(self, target: InvestigationTarget) -> Diagnosis:
        """Investigate one target and report what was found and concluded.

        A fresh ``Retrieved`` and ``Consulted`` per call is what scopes both
        citations and claimed coverage to this investigation: an identifier the
        model remembers from another incident resolves to nothing, and a signal
        consulted last time is not one consulted this time.

        Args:
            target: What to investigate.

        Returns:
            The findings whose evidence the platform actually returned, the
            signals consulted to gather them, and the conclusion drawn across
            them.

        Raises:
            InvestigatorError: The investigation could not be completed — the
                manager errored, or nothing could be retrieved at all.
        """
        retrieved = Retrieved(link=self._links)
        consulted = Consulted(offered=self._crew, retrieved=retrieved)
        concluded = self._concluded(target, consulted, retrieved)
        if retrieved.failures and not retrieved.retrievals:
            raise InvestigatorError(
                f"No evidence could be gathered for {target.service}: "
                f"{'; '.join(retrieved.failures)}"
            )
        findings = Findings(
            findings=consulted.findings,
            retrieval_failures=retrieved.failures + consulted.refusals,
            consulted=consulted.signals,
        )
        _log.info(
            "Investigated %s: consulted %s, %d finding(s)",
            target.service,
            ", ".join(consulted.order) or "nobody",
            len(findings.findings),
        )
        return self._worded(target, findings, concluded)

    def _concluded(
        self,
        target: InvestigationTarget,
        consulted: Consulted,
        retrieved: Retrieved,
    ) -> dict[str, Any]:
        """Run the manager over the crew, and say what it concluded."""
        try:
            return self._run_diagnostician(
                self._crew, consulted, retrieved, target.describe()
            )
        except Exception as error:
            raise InvestigatorError(
                f"The investigation of {target.service} failed: {error}"
            ) from error

    def _worded(
        self,
        target: InvestigationTarget,
        findings: Findings,
        concluded: dict[str, Any],
    ) -> Diagnosis:
        """Turn what was found and concluded into the account a reader receives.

        The conclusion is offered to ``Diagnosis`` rather than decided here:
        that value drops a hypothesis with no surviving finding beneath it, and
        it is the last place the discipline can still be applied.
        """
        hypothesis = _hypothesis_in(concluded)
        confidence = _confidence_in(concluded)
        headline, narrative = self._words(target, findings, hypothesis, confidence)
        return Diagnosis(
            headline=headline,
            account=(
                account.compose(narrative, findings, confidence)
                if narrative
                else account.without_words(hypothesis, confidence, findings)
            ),
            hypothesis=hypothesis,
            confidence=confidence,
            findings=findings,
        )

def _hypothesis_in(concluded: Any) -> str | None:
    """What the manager concluded, or ``None`` where it said nothing usable."""
    if not isinstance(concluded, dict):
        return None
    hypothesis = concluded.get("hypothesis")
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        return None
    return hypothesis.strip()


def _confidence_in(concluded: Any) -> Confidence | None:
    """The declared level the manager named, or ``None`` if it named another.

    A level outside the declared set is reported as no level, for the reason an
    unresolvable citation drops a finding: a confidence nobody can compare is
    not a confidence, and inventing a nearest match would be this system putting
    words in its own mouth.
    """
    if not isinstance(concluded, dict):
        return None
    named = concluded.get("confidence")
    try:
        return Confidence(named) if isinstance(named, str) else None
    except ValueError:
        _log.warning(
            "The diagnostician named a confidence level nobody declared: %r",
            named,
        )
        return None


def _one_line(headline: Any) -> str:
    """Flatten whatever the writer produced into the one line a channel carries."""
    if not isinstance(headline, str):
        return ""
    return " ".join(headline.split())


def run_with_adk(deployment: Deployment) -> RunDiagnostician:
    """Drive the manager with a real model over a real crew.

    ADK is asynchronous underneath; the event loop is owned here so that the
    port, the run, and the composition root all stay synchronous.

    Args:
        deployment: Where the platform is, how to authenticate, and what an
            agent reasons on when it names no model of its own.

    Returns:
        A callable that runs one investigation's manager and returns what it
        concluded.
    """

    def _run(
        crew: Sequence[Specialist],
        consulted: Consulted,
        retrieved: Retrieved,
        prompt: str,
    ) -> dict[str, Any]:
        agent = build_manager(crew, deployment, consulted, retrieved)
        _log.info("Running the diagnostician over %d specialist(s)", len(crew))
        return asyncio.run(run_agent(agent, prompt))

    return _run


async def run_agent(agent: Any, prompt: str) -> dict[str, Any]:
    """Run one agent to completion and hand back its structured answer.

    The framework primitive both drivers are built on, and the seam an
    integration test drives a lone agent through against a fake platform. Public
    for that reason: what it does is run an agent, which is a thing worth being
    able to do on its own.
    """
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
    """Read the structured answer out of a final event, if it carries any."""
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
