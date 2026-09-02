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
    CONSULT_THE_PLATFORM,
    METRIC_QUERY_DIALECT,
    SKILL_LIST_TOOL,
    SKILL_LOAD_TOOL,
)
from alert_triage.investigation.adapters.datadog.mcp import DATADOG
from alert_triage.investigation.adapters.datadog.preview import (
    APM_TOOLSET_AVAILABLE,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset

CORE_TOOLSET = "core"
APM_TOOLSET = "apm"
"""The toolsets on the platform's server holding what this specialist reaches.

``apm`` is reached only where the account has it; see ``preview``.
"""

METRIC_TOOL = "get_datadog_metric"
METRIC_SEARCH_TOOL = "search_datadog_metrics"
METRIC_CONTEXT_TOOL = "get_datadog_metric_context"
DEPENDENCIES_TOOL = "search_datadog_service_dependencies"
EVENTS_TOOL = "search_datadog_events"
"""The tools every account has, whatever its Preview access.

``METRIC_SEARCH_TOOL`` is what keeps a guessed metric name from reading as a
healthy service. A metric query the platform has never heard of comes back
empty, and an empty answer is deliberately not a failure — so without a way to
ask which metrics a service actually reports, the specialist cannot tell "this
service is fine" from "I made that name up".

``METRIC_CONTEXT_TOOL`` is the second half of that: it takes one metric name
and answers with its unit, its type and the tags it carries. It enumerates
nothing, and a specialist told otherwise asks it for a service's whole
catalogue — which it has no argument for, so the retrieval is refused.

``EVENTS_TOOL`` carries deploy correlation on an account without Preview. It
returns deployments, infrastructure changes and monitor alerts rather than the
change stories assembled for an APM service: coarser, and enough, because the
question is whether something landed near the alerts rather than what it
consisted of.
"""

BOTTLENECK_TOOL = "apm_latency_bottleneck_summary"
WATCHDOG_TOOL = "apm_search_watchdog_stories"
CHANGES_TOOL = "get_change_stories"
CHANGE_SEARCH_TOOL = "semantic_search_change_stories"
"""The tools that exist only in the Preview toolset, reached only where granted.

That these names exist and that the filter admits them is what the
credential-gated live run establishes; a fake is built from the same
assumptions this declaration is.
"""

_CORE_TOOLS_DESCRIBED = f"""\
- `{METRIC_SEARCH_TOOL}` lists the metrics that exist, filtered by name or by
  tag — `service:the-service` is how you narrow it to one service's.
- `{METRIC_CONTEXT_TOOL}` takes one metric you have already found and tells
  you its unit, its type and what tags it carries.
- `{METRIC_TOOL}` returns a metric's values over a time range.
- `{DEPENDENCIES_TOOL}` names the service's immediate upstream and downstream
  neighbours."""

_PREVIEW_TOOLS_DESCRIBED = f"""\
- `{BOTTLENECK_TOOL}` breaks a service's latency down into where the time was
  spent, when you have seen latency move and want to say where it went.
- `{WATCHDOG_TOOL}` returns the anomalies the platform itself already detected
  for a service over a time range.
- `{CHANGES_TOOL}` returns the deployments, feature-flag changes and
  configuration changes recorded for a service over a time range.
- `{CHANGE_SEARCH_TOOL}` searches those same changes in plain language, for
  when you want the ones that could plausibly explain a movement you have
  already observed rather than all of them."""

_EVENTS_DESCRIBED = f"""\
- `{EVENTS_TOOL}` returns the events recorded around a service — deployments,
  infrastructure changes and monitor alerts — which is how you find out
  whether something landed near the alerts."""

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


def _tools_described(preview: bool) -> str:
    """The tools this specialist is told it has, given what the account may reach."""
    return "\n".join(
        (
            _CORE_TOOLS_DESCRIBED,
            _PREVIEW_TOOLS_DESCRIBED if preview else _EVENTS_DESCRIBED,
        )
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

{_tools_described(preview)}

{CONSULT_THE_PLATFORM}

Ask `{METRIC_SEARCH_TOOL}` which metrics the service reports before you query
one, and read the name you query out of what it answers. Do not guess a metric
name: a name this service does not report comes back empty, and an empty
answer means the service does not report it, which is not the same as the
service being healthy. If you find yourself reporting that a signal was quiet,
be sure you asked for a metric that exists.

{METRIC_QUERY_DIALECT}

What to report:

{_what_to_report(preview)}

Rules you must follow:

- Retrieve before you report. You may retrieve more than once, narrowing what
  you ask for as you learn how the service is instrumented.
- Every result you are given back is identified. A retrieval is `call-N`, and
  each individual entry within it is `call-N/item-M`. Cite what shows your
  observation: `call-N/item-M` for entries you read it from, and `call-N` for
  an aggregate — a latency breakdown, a dependency map — where there are no
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
    if preview:
        return _declared(
            Toolset(
                provider=DATADOG,
                name=CORE_TOOLSET,
                tools=(
                    METRIC_TOOL,
                    METRIC_SEARCH_TOOL,
                    METRIC_CONTEXT_TOOL,
                    DEPENDENCIES_TOOL,
                    SKILL_LIST_TOOL,
                    SKILL_LOAD_TOOL,
                ),
            ),
            Toolset(
                provider=DATADOG,
                name=APM_TOOLSET,
                tools=(
                    BOTTLENECK_TOOL,
                    WATCHDOG_TOOL,
                    CHANGES_TOOL,
                    CHANGE_SEARCH_TOOL,
                ),
            ),
            preview=preview,
        )

    return _declared(
        Toolset(
            provider=DATADOG,
            name=CORE_TOOLSET,
            tools=(
                METRIC_TOOL,
                METRIC_SEARCH_TOOL,
                METRIC_CONTEXT_TOOL,
                DEPENDENCIES_TOOL,
                EVENTS_TOOL,
                SKILL_LIST_TOOL,
                SKILL_LOAD_TOOL,
            ),
        ),
        preview=preview,
    )


def _declared(*toolsets: Toolset, preview: bool) -> Specialist:
    """The declaration around the toolsets the account turned out to have.

    Args:
        toolsets: What this account's specialist may reach.
        preview: Whether those include the Preview toolset, which is what the
            instruction is written against.

    Returns:
        The declaration, with the instruction matching the tools.
    """
    return Specialist(
        name="apm_specialist",
        signal=Signal.APM,
        instruction=_instruction(preview),
        output_schema=ReportedFindings,
        toolsets=toolsets,
    )


APM_SPECIALIST = apm_specialist(preview=APM_TOOLSET_AVAILABLE)
"""The APM specialist as the crew sees it: one declaration, nothing else."""

APM_INSTRUCTION = APM_SPECIALIST.instruction
"""What the specialist is asked, for the access this deployment actually has."""
