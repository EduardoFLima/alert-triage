"""Manager-driven investigation over all specialists.

Retrieved and Consulted are per run, so citations and coverage cannot leak.
A bound with findings returns incomplete; a bound with nothing raises for retry.
"""

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine, Iterable, Sequence
from typing import Any

from alert_triage.configuration.settings import CircuitBreakers
from alert_triage.investigation.adapters.adk.agent import (
    Deployment,
    build_manager,
    build_reasoner,
)
from alert_triage.investigation.adapters.adk.bounds import Bounds
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
from alert_triage.investigation.domain.account import FindingPage
from alert_triage.investigation.domain.specialist import Specialist
from alert_triage.investigation.ports.investigator import InvestigatorError
from alert_triage.shared import journal

_log = logging.getLogger(__name__)

RunDiagnostician = Callable[
    [Sequence[Specialist], Consulted, Retrieved, str], dict[str, Any]
]
"""Injected so tests can assert what the manager was offered and consulted."""

RunReport = Callable[[str], dict[str, Any]]


class AdkInvestigator:
    def __init__(
        self,
        *,
        crew: Sequence[Specialist],
        run_diagnostician: RunDiagnostician,
        run_report: RunReport,
        links: Links | None = None,
        breakers: CircuitBreakers | None = None,
    ) -> None:
        self._crew = tuple(crew)
        self._run_diagnostician = run_diagnostician
        self._run_report = run_report
        self._links = links
        self._breakers = breakers or CircuitBreakers()

    def investigate(self, target: InvestigationTarget) -> Diagnosis:
        bounds = Bounds(self._breakers)
        retrieved = Retrieved(link=self._links, service=target.service, env=target.env)
        consulted = Consulted(offered=self._crew, retrieved=retrieved, bounds=bounds)
        concluded = self._concluded(target, consulted, retrieved)
        if retrieved.failures and not retrieved.retrievals:
            raise InvestigatorError(
                f"No evidence could be gathered for {target.service}: "
                f"{'; '.join(retrieved.failures)}"
            )
        if bounds.reached and not consulted.findings:
            raise InvestigatorError(
                f"The investigation of {target.service} was stopped before it "
                f"found anything: {'; '.join(bounds.reached)}"
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
        headline, narrative = self._words(target, findings, hypothesis, confidence)
        page = self._service_page(target)
        return Diagnosis(
            headline=headline,
            account=(
                account.compose(narrative, findings, confidence, page)
                if narrative
                else account.without_words(hypothesis, confidence, findings, page)
            ),
            hypothesis=hypothesis,
            confidence=confidence,
            findings=findings,
        )

    def _service_page(self, target: InvestigationTarget) -> FindingPage | None:
        links = self._links
        if links is None:
            return None
        return lambda finding: links.to_service(
            target.service, target.window, finding.section, target.env
        )

    def _words(
        self,
        target: InvestigationTarget,
        findings: Findings,
        hypothesis: str | None,
        confidence: Confidence | None,
    ) -> tuple[str, str]:
        """A wording failure costs prose only; checked findings already exist."""
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
    return ", ".join(signal.value for signal in findings.consulted)


def _hypothesis_in(concluded: Any) -> str | None:
    if not isinstance(concluded, dict):
        return None
    hypothesis = concluded.get("hypothesis")
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        return None
    return hypothesis.strip()


def _confidence_in(concluded: Any) -> Confidence | None:
    """Unknown confidence is none rather than this system inventing a match."""
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
    if not isinstance(headline, str):
        return ""
    return " ".join(headline.split())


def run_with_adk(deployment: Deployment) -> RunDiagnostician:
    """ADK is async underneath; this adapter keeps the port synchronous."""

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
        return asyncio.run(run_bounded(run_agent(agent, prompt), consulted.bounds))

    return _run


async def run_bounded(
    run: Coroutine[Any, Any, dict[str, Any]], bounds: Bounds
) -> dict[str, Any]:
    """Backstops hangs between tool calls, where callback deadlines cannot fire.

    Cancellation preserves Retrieved and Consulted because the investigator owns them.
    """
    try:
        async with asyncio.timeout(bounds.remaining):
            return await run
    except TimeoutError:
        bounds.reach(
            "the investigation was stopped: it did not conclude within its "
            f"{bounds.duration} seconds"
        )
        return {}


def report_with_adk(deployment: Deployment) -> RunReport:
    def _run(brief: str) -> dict[str, Any]:
        agent = build_reasoner(REPORT_WRITER, deployment)
        _log.info(journal.event("the report is being worded"))
        return asyncio.run(run_agent(agent, brief))

    return _run


async def run_agent(agent: Any, prompt: str) -> dict[str, Any]:
    """Public so integration tests can drive one ADK agent through a fake platform."""
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
    """ADK may mark several events final when multiple agents run together.

    Filter by author and keep that agent's last structured answer.
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
