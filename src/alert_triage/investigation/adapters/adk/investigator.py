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
import json
import logging
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from alert_triage.investigation.adapters.adk.agent import (
    Deployment,
    build_manager,
    build_reasoner,
)
from alert_triage.investigation.adapters.adk.consultation import Consulted
from alert_triage.investigation.adapters.adk.evidence import Links, Retrieved
from alert_triage.investigation.adapters.crew.reasoners.report import REPORT_WRITER
from alert_triage.investigation.contract import (
    Confidence,
    Diagnosis,
    Findings,
    InvestigationTarget,
)
from alert_triage.investigation.domain import account
from alert_triage.investigation.domain.specialist import Specialist
from alert_triage.investigation.ports.investigator import InvestigatorError
from alert_triage.shared import journal

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

RunReport = Callable[[str], dict[str, Any]]
"""How the account is worded: given a brief, answer with a headline and a body."""


class AdkInvestigator:
    """An investigation routed by a manager over a crew, behind the port."""

    def __init__(
        self,
        *,
        crew: Sequence[Specialist],
        run_diagnostician: RunDiagnostician,
        run_report: RunReport,
        links: Links | None = None,
    ) -> None:
        """Build an investigator over one crew, one manager, and one writer.

        Args:
            crew: The specialists to offer, every one of them.
            run_diagnostician: How the manager is driven for one target.
            run_report: How the account is worded once there is one to word.
            links: How this deployment's platform addresses what it returns.
                Absent, evidence is gathered and reported without addresses.
        """
        self._crew = tuple(crew)
        self._run_diagnostician = run_diagnostician
        self._run_report = run_report
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
        hypothesis = _hypothesis_in(concluded)
        confidence = _confidence_in(concluded)
        _log.info(
            journal.banner(
                "INVESTIGATION CONCLUDED",
                target.service,
                consulted=", ".join(consulted.order) or "nobody",
                signals=", ".join(signal.value for signal in findings.consulted),
                findings=len(findings.findings),
                incomplete=", ".join(findings.retrieval_failures) or None,
                hypothesis=hypothesis or "none reached",
                confidence=confidence.value if confidence else "none",
            )
        )
        return self._worded(target, findings, hypothesis, confidence)

    def _concluded(
        self,
        target: InvestigationTarget,
        consulted: Consulted,
        retrieved: Retrieved,
    ) -> dict[str, Any]:
        """Run the manager over the crew, and say what it concluded."""
        try:
            concluded = self._run_diagnostician(
                self._crew, consulted, retrieved, target.describe()
            )
        except Exception as error:
            raise InvestigatorError(
                f"The investigation of {target.service} failed: {error}"
            ) from error
        if not concluded:
            _log.warning(
                journal.event(
                    "the diagnostician reached no conclusion",
                    "Its findings still stand and are reported; what is missing "
                    "is the reasoning across them.",
                    service=target.service,
                )
            )
        return concluded

    def _worded(
        self,
        target: InvestigationTarget,
        findings: Findings,
        hypothesis: str | None,
        confidence: Confidence | None,
    ) -> Diagnosis:
        """Turn what was found and concluded into the account a reader receives.

        The conclusion is offered to ``Diagnosis`` rather than decided here:
        that value drops a hypothesis with no surviving finding beneath it, and
        it is the last place the discipline can still be applied.
        """
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

    def _words(
        self,
        target: InvestigationTarget,
        findings: Findings,
        hypothesis: str | None,
        confidence: Confidence | None,
    ) -> tuple[str, str]:
        """What the report agent wrote, or what this project writes without it.

        A wording failure costs the report its prose and nothing else. What it
        carries was gathered before any of it was worded, so losing the report
        over the last and least consequential step would be the worst trade this
        investigation could make.
        """
        fallback = account.headline_for(target.service, findings)
        try:
            worded = self._run_report(_brief(target, findings, hypothesis, confidence))
        except Exception as error:
            _log.warning(
                journal.event(
                    "the report could not be worded",
                    service=target.service,
                    detail=str(error),
                    instead="composed from what was found",
                )
            )
            return fallback, ""
        headline = _one_line(
            worded.get("headline") if isinstance(worded, dict) else None
        )
        narrative = worded.get("narrative") if isinstance(worded, dict) else None
        if not headline or not isinstance(narrative, str) or not narrative.strip():
            _log.warning(
                journal.event(
                    "the report agent answered unusably",
                    service=target.service,
                    instead="composed from what was found",
                )
            )
            return fallback, ""
        return headline, narrative


def _brief(
    target: InvestigationTarget,
    findings: Findings,
    hypothesis: str | None,
    confidence: Confidence | None,
) -> str:
    """Everything the writer needs, and nothing it could mistake for evidence."""
    return "\n".join(
        [
            target.describe(),
            f"Signals examined: {_named_signals(findings) or 'none'}",
            f"Hypothesis: {hypothesis or 'none reached'}",
            f"Confidence: {confidence.value if confidence else 'none'}",
            "",
            *account.evidence_lines(findings),
        ]
    )


def _named_signals(findings: Findings) -> str:
    """The signals consulted, named for the writer that must not exceed them."""
    return ", ".join(signal.value for signal in findings.consulted)


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
            journal.event(
                "the diagnostician named a confidence nobody declared",
                named=repr(named),
                declared=", ".join(level.value for level in Confidence),
            )
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
        _log.info(
            journal.event(
                "the specialists crew",
                crew=", ".join(specialist.name for specialist in crew),
            )
        )
        return asyncio.run(run_agent(agent, prompt))

    return _run


def report_with_adk(deployment: Deployment) -> RunReport:
    """Drive the report agent with a real model and no tools at all.

    Args:
        deployment: What an agent reasons on when it names no model of its own.

    Returns:
        A callable that words one account.
    """

    def _run(brief: str) -> dict[str, Any]:
        agent = build_reasoner(REPORT_WRITER, deployment)
        _log.info(journal.event("the report is being worded"))
        return asyncio.run(run_agent(agent, brief))

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
    events = []
    async for event in runner.run_async(
        user_id="alert-triage",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        events.append(event)
    return answer_in(events, getattr(agent, "name", ""))


def answer_in(events: Iterable[Any], author: str) -> dict[str, Any]:
    """The structured answer one agent gave, out of everything the run produced.

    More than one event can be called final once several agents take part in one
    invocation, which the framework says outright. Reading the last of them
    indiscriminately is how a conclusion the model did reach goes missing.

    Two filters, and both are needed. The author, so a specialist's own report —
    a perfectly good record, with no hypothesis in it — is never mistaken for
    the manager's answer. And the content, so an event with nothing to read
    leaves what was already found alone.

    Args:
        events: Everything the run produced, in order.
        author: The agent whose answer is wanted.

    Returns:
        The last structured answer that agent gave, or an empty record where it
        gave none. Empty means the agent never answered in its schema, which is
        a different fact from an agent that answered with nothing to say, and
        the caller is expected to tell them apart.
    """
    answer: dict[str, Any] = {}
    for event in events:
        if getattr(event, "author", None) != author:
            continue
        if not (
            getattr(event, "is_final_response", None) and event.is_final_response()
        ):
            continue
        payload = _payload(event)
        if payload:
            answer = payload
    return answer


def _payload(event: Any) -> dict[str, Any]:
    """Read the structured answer out of an event, if it carries one."""
    content = getattr(event, "content", None)
    for part in getattr(content, "parts", None) or ():
        text = getattr(part, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}
