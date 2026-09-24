"""The APM specialist, declared: its tools, its instruction, and its schema.

Golden signals first, then the two questions an engineer asks straight after
them: what the service's immediate neighbours were doing, and whether anything
landed just before the alerts. Both are tools on this platform rather than
inferences, which is why they are declarations here and not code.

What it reaches depends on one thing outside it: whether the account has
Datadog's Preview ``apm`` toolset. Without it the specialist still reports the
golden signals, the neighbours, and what changed — the last through raw events
rather than change stories, which is coarser and still answers "did this start
after a deploy". What it cannot do without it is say where the latency went, or
report what the platform had already noticed on its own; ``core`` offers no
substitute for either, so those asks leave the instruction entirely rather than
becoming tools the model is told about and cannot call.

Everything is a module constant or built from one, so that what the specialist
asks for can be asserted by a unit test without constructing an agent or
reaching a model. As with every specialist, the output schema offers no field
an agent could write evidence into: it cites what it was shown, at either
grain.
"""

from pydantic import BaseModel, Field

from alert_triage.investigation.adapters.datadog.dialect import (
    AN_EMPTY_ANSWER,
    CONSULT_THE_PLATFORM,
    METRIC_QUERY_DIALECT,
)
from alert_triage.investigation.adapters.datadog.preview import (
    APM_TOOLSET_AVAILABLE,
)
from alert_triage.investigation.adapters.datadog.tools import (
    GET_CHANGE_STORIES,
    GET_METRIC,
    GET_METRIC_CONTEXT,
    LATENCY_BOTTLENECK_SUMMARY,
    LIST_SKILLS,
    LOAD_SKILL,
    SEARCH_CHANGE_STORIES,
    SEARCH_ENTITIES,
    SEARCH_EVENTS,
    SEARCH_METRICS,
    SEARCH_WATCHDOG_STORIES,
    DatadogTool,
    described,
    toolsets,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal
from alert_triage.investigation.domain.specialist import Specialist

_METRIC_TOOLS = (SEARCH_METRICS, GET_METRIC_CONTEXT, GET_METRIC)
"""The metric tools every account has, whatever its Preview access."""

_PREVIEW_TOOLS = (
    LATENCY_BOTTLENECK_SUMMARY,
    SEARCH_WATCHDOG_STORIES,
    GET_CHANGE_STORIES,
    SEARCH_CHANGE_STORIES,
)
"""The tools that exist only in the Preview toolset, reached only where granted.

That these names exist and that the filter admits them is what the
credential-gated live run establishes; a fake is built from the same
assumptions this declaration is.
"""

_WITHOUT_PREVIEW_TOOLS = (SEARCH_EVENTS,)
"""What carries deploy correlation on an account without Preview.

Events are deployments, infrastructure changes and monitor alerts rather than
the change stories assembled for an APM service: coarser, and enough, because
the question is whether something landed near the alerts rather than what it
consisted of.
"""

_CATALOGUE_ASK = """\
The catalogue answers what you ask, so ask it for the immediate upstream and
downstream dependencies of the service you were told about, and not about its
neighbours in turn."""
"""What to ask the catalogue search, which would otherwise be asked anything.

It follows the list directly, and the catalogue search is listed last, so the
ask sits beside the tool it is about.
"""

_WATCHDOG_ASK = """\
- Anything the platform already flagged for this service over the window. It
  detected it independently of you, so it is worth reporting whether or not it
  matches what you went looking for."""

_BOTTLENECK_ASK = """\
- Where the latency went, once you have seen it move: which part of the
  service's own work the time was actually spent in."""

_GOLDEN_SIGNALS_ASK = """\
- The golden signals over the window, and when each movement began relative to
  the alerts. If they held steady, say so — an unremarkable service is a
  useful answer."""

_NEIGHBOURS_ASK = """\
- What the service's immediate neighbours were doing over the same window,
  where the platform can say. Go one hop only: a neighbour is context for this
  service's behaviour, and you are not investigating it. Do not investigate a
  neighbour in its own right, and do not follow the dependency graph beyond
  those immediate neighbours."""

_CHANGE_ASK = """\
- Whether a change to the service landed close enough to the alerts to be
  worth a reader's attention, and when it landed. A change near the alerts is
  a coincidence in time that you observed. It is not a cause, and you must not
  present it as one."""


def _tools(preview: bool) -> tuple[DatadogTool, ...]:
    """The tools this specialist may call, given what the account may reach."""
    return (
        *_METRIC_TOOLS,
        *(_PREVIEW_TOOLS if preview else _WITHOUT_PREVIEW_TOOLS),
        SEARCH_ENTITIES,
    )


def _what_to_report(preview: bool) -> str:
    """What it is asked to report, minus anything it has no tool to establish."""
    asks = (
        (_WATCHDOG_ASK,) if preview else (),
        (_GOLDEN_SIGNALS_ASK,),
        (_BOTTLENECK_ASK,) if preview else (),
        (_NEIGHBOURS_ASK, _CHANGE_ASK),
    )
    return "\n".join(ask for group in asks for ask in group)


def _instruction(preview: bool) -> str:
    """What this specialist is asked to look for, in the terms of this platform."""
    return f"""
You are an APM specialist doing the first-pass investigation a knowledgeable
engineer would do for a service that has started alerting.

You will be told a service and the window its alerts span. Report what that
service's golden signals — latency, error rate and throughput — did over that
window: what moved, by how much, and when it moved relative to the alerts.

The tools you have are Datadog's:

{described(*_tools(preview))}

{_CATALOGUE_ASK}

{CONSULT_THE_PLATFORM}

Ask `{SEARCH_METRICS.name}` which metrics the service reports before you query
one, and read the name you query out of what it answers. Do not guess a metric
name: a name this service does not report comes back empty.

{AN_EMPTY_ANSWER}

{METRIC_QUERY_DIALECT}

What to report:

{_what_to_report(preview)}

Rules you must follow:

- Retrieve before you report. You may retrieve more than once, narrowing what
  you ask for as you learn how the service is instrumented.
- Every result you are given back is identified. A retrieval is `call-N`, and
  each individual entry within it is `call-N/item-M`. Cite what shows your
  observation: `call-N/item-M` for entries you read it from, and `call-N` for
  an aggregate — a metric's series, a latency breakdown — where there are no
  individual entries to point at. Cite at most {MAX_EXAMPLES_PER_FINDING} per
  observation, choosing ones that represent what you observed. An observation
  citing neither will be discarded.
- Never write out a metric value, a dependency or a change yourself. You cite
  what you were shown; you do not compose it. An observation citing something
  you were not shown will be discarded.
- If a retrieval comes back saying it failed, it means the retrieval did not
  run. It does not mean the service was steady, and you must not report it as
  steady or conclude anything at all about the service from it. Try another
  retrieval, and report only what the retrievals that succeeded show.
- Report only movements you actually observed in retrieved evidence. If the
  service was unremarkable through the window, report no findings at all.
- Do not name a root cause, offer a hypothesis, state a confidence level, or
  recommend an action. Another agent reasons across signals and concludes;
  your job is to say accurately what this service's performance shows.
""".strip()


class ApmFinding(BaseModel):
    """One movement the agent observed, with what it rests on."""

    observation: str = Field(
        description=(
            "What was observed: what moved, by how much, and when it moved "
            "relative to the alerts."
        )
    )
    occurrences: int = Field(
        description="How many retrieved points or entries show it.", ge=0
    )
    cites: list[str] = Field(
        description=(
            "What shows this observation, by the identifiers you were given: "
            "`call-N/item-M` for individual entries, `call-N` for an aggregate. "
            f"At most {MAX_EXAMPLES_PER_FINDING} of them."
        )
    )


class ReportedFindings(BaseModel):
    """Everything the agent has to report about one incident's golden signals."""

    findings: list[ApmFinding] = Field(
        default_factory=list,
        description="What was observed. Empty when the service was unremarkable.",
    )


def apm_specialist(*, preview: bool) -> Specialist:
    """Declare the APM specialist for an account with or without Preview access.

    Args:
        preview: Whether the account may reach the ``apm`` toolset.

    Returns:
        The declaration, reaching only tools the account can actually call and
        instructed only in what those tools can establish.
    """
    return Specialist(
        name="apm_specialist",
        signal=Signal.APM,
        instruction=_instruction(preview),
        output_schema=ReportedFindings,
        toolsets=toolsets(*_tools(preview), LIST_SKILLS, LOAD_SKILL),
    )


APM_SPECIALIST = apm_specialist(preview=APM_TOOLSET_AVAILABLE)
"""The APM specialist as the crew sees it: one declaration, nothing else."""

APM_INSTRUCTION = APM_SPECIALIST.instruction
"""What the specialist is asked, for the access this deployment actually has."""
