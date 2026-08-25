"""The APM specialist, declared: its tools, its instruction, and its schema.

Golden signals first, then the two questions an engineer asks straight after
them: what the service's immediate neighbours were doing, and whether anything
landed just before the alerts. Both are tools on this platform rather than
inferences, which is why they are declarations here and not code.

The first specialist to reach two toolsets. ``core`` holds the metric and
dependency tools every account has; ``apm`` holds the two that make the
difference between reporting that latency rose and reporting where it went.

Everything is a module constant so that what the specialist asks for can be
asserted by a unit test without constructing an agent or reaching a model. As
with every specialist, the output schema offers no field an agent could write
evidence into: it cites what it was shown, at either grain.
"""

from pydantic import BaseModel, Field

from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset

CORE_TOOLSET = "core"
APM_TOOLSET = "apm"
"""The toolsets on the platform's server holding what this specialist reaches.

``apm`` is marked Preview by the platform. That is a live-test failure waiting
to happen rather than a reason to avoid it: without it the specialist reports
that latency moved and never where the time went.
"""

METRIC_TOOL = "get_datadog_metric"
DEPENDENCIES_TOOL = "search_datadog_service_dependencies"
BOTTLENECK_TOOL = "apm_latency_bottleneck_summary"
CHANGES_TOOL = "get_change_stories"
"""The tools this specialist may reach, and the only ones.

That these names exist and that the filter admits them is what the
credential-gated live run establishes; a fake is built from the same
assumptions this declaration is.
"""

APM_INSTRUCTION = f"""
You are an APM specialist doing the first-pass investigation a knowledgeable
engineer would do for a service that has started alerting.

You will be told a service and the window its alerts span. Report what that
service's golden signals — latency, error rate and throughput — did over that
window: what moved, by how much, and when it moved relative to the alerts.

The tools you have are Datadog's:

- `{METRIC_TOOL}` returns a metric's values over a time range.
- `{BOTTLENECK_TOOL}` breaks a service's latency down into where the time was
  spent, when you have seen latency move and want to say where it went.
- `{DEPENDENCIES_TOOL}` names the service's immediate upstream and downstream
  neighbours.
- `{CHANGES_TOOL}` returns the deployments, feature-flag changes and
  configuration changes recorded for a service over a time range.

A metric query is an aggregator, a metric name, and a scope in braces:
`avg:trace.http.request.duration{{service:checkout}}`, with
`sum:trace.http.request.errors{{service:checkout}}.as_count()` for a count and
`p95:` where an average would hide the tail. Always scope the query to the
service you were told about and the window you were given.

What to report:

- The golden signals over the window, and when each movement began relative to
  the alerts. If they held steady, say so — an unremarkable service is a
  useful answer.
- What the service's immediate neighbours were doing over the same window,
  where the platform can say. Go one hop only: a neighbour is context for this
  service's behaviour, and you are not investigating it. Do not investigate a
  neighbour in its own right, and do not follow the dependency graph beyond
  those immediate neighbours.
- Whether a change to the service landed close enough to the alerts to be
  worth a reader's attention, and when it landed. A change near the alerts is
  a coincidence in time that you observed. It is not a cause, and you must not
  present it as one.

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


APM_SPECIALIST = Specialist(
    name="apm_specialist",
    signal=Signal.APM,
    instruction=APM_INSTRUCTION,
    output_schema=ReportedFindings,
    toolsets=(
        Toolset(name=CORE_TOOLSET, tools=(METRIC_TOOL, DEPENDENCIES_TOOL)),
        Toolset(name=APM_TOOLSET, tools=(BOTTLENECK_TOOL, CHANGES_TOOL)),
    ),
)
"""The APM specialist as the crew sees it: one declaration, nothing else."""
