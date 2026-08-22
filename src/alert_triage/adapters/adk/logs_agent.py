"""The Logs specialist: one agent, one dimension, one tool.

The instruction is a module constant so that what the agent is asked for can be
asserted by a unit test without constructing an agent or reaching a model. It
names no platform: the tool it is given speaks this project's vocabulary, which
is what lets slice 7 point the same agent at another observability platform
without a word of it changing.

The output schema is the other half of the evidence discipline described in
``evidence``. There is no field here an agent could write a log line into; it
reports what it observed and cites the identifiers of the records it was shown.
"""

from collections.abc import Callable
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from pydantic import BaseModel, Field

from alert_triage.domain.findings import MAX_EXAMPLES_PER_FINDING
from alert_triage.domain.incident import Incident

SearchLogs = Callable[[str, str, str, str], list[dict[str, Any]]]
"""The one tool the Logs agent is given, as ADK will see it."""

LOGS_INSTRUCTION = f"""
You are a logs specialist doing the first-pass investigation a knowledgeable
engineer would do for a service that has started alerting.

You will be told a service and the window its alerts span. Search that
service's logs over that window and report the error and warning patterns you
find: what recurs, how often, and when it started relative to the alerts.

Rules you must follow:

- Search before you report. You may search more than once, narrowing your
  query as you learn what the service is logging.
- Every observation must cite the records that show it, by the `id` field of
  the records the search returned. Cite at most {MAX_EXAMPLES_PER_FINDING}
  records per observation, choosing ones that represent the pattern.
- Never write out a log line yourself. You cite records; you do not compose
  them. An observation whose citations are not records the search returned
  will be discarded.
- Report only patterns you actually observed in retrieved logs. If the logs
  are quiet, report no findings at all — that is a useful answer, not a
  failure.
- Do not name a root cause, offer a hypothesis, state a confidence level, or
  recommend an action. Another agent reasons across signals and concludes;
  your job is to say accurately what the logs show.
""".strip()


class LogsFinding(BaseModel):
    """One pattern the agent observed, with the records it rests on."""

    observation: str = Field(
        description="What was observed: the pattern, its rate, and when it began."
    )
    occurrences: int = Field(
        description="How many matching records were seen in total.", ge=0
    )
    cites: list[str] = Field(
        description=(
            "The `id` values of the retrieved records that show this pattern, "
            f"at most {MAX_EXAMPLES_PER_FINDING} of them."
        )
    )


class ReportedFindings(BaseModel):
    """Everything the agent has to report about one incident's logs."""

    findings: list[LogsFinding] = Field(
        default_factory=list,
        description="The patterns observed. Empty when the logs were quiet.",
    )


def describe(incident: Incident) -> str:
    """State the incident to the agent in the terms its tool takes.

    The window comes from the alerts rather than from the run, so evidence is
    gathered around the problem rather than around whichever run noticed it.
    """
    window = incident.window
    return (
        f"Service: {incident.service}\n"
        f"Window start: {window.start.isoformat()}\n"
        f"Window end: {window.end.isoformat()}\n"
        f"Alerts in this incident: {len(incident.alerts)}"
    )


def build_logs_agent(*, model: str | BaseLlm, search_logs: SearchLogs) -> LlmAgent:
    """Build the Logs specialist around the one tool it is allowed.

    Args:
        model: The model the agent reasons with — a name, or one already
            built and told how to authenticate.
        search_logs: The log search, already bound to the observability
            platform and to this investigation's record keeping.

    Returns:
        The agent, with that tool and no other.
    """
    return LlmAgent(
        name="logs_specialist",
        model=model,
        instruction=LOGS_INSTRUCTION,
        tools=[search_logs],
        output_schema=ReportedFindings,
    )
