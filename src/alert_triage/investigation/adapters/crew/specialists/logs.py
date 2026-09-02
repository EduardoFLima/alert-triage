"""The Logs specialist, declared: its tools, its instruction, and its schema.

The instruction names Datadog's log tools and Datadog's query dialect, and
that is deliberate rather than a leak. The model composes the query, a query
dialect is not translatable between platforms, and the boundary that pretended
otherwise is what this slice removed. A second platform's logs specialist is a
declaration of its own — a contribution, not a migration.

Everything here is a module constant so that what the specialist asks for can
be asserted by a unit test without constructing an agent or reaching a model.

The output schema is the other half of the evidence discipline described in
``evidence``. There is no field an agent could write a log line into: it
reports what it observed and cites the identifiers of what it was shown, at
either grain.
"""

from pydantic import BaseModel, Field

from alert_triage.investigation.adapters.datadog.dialect import (
    CONSULT_THE_PLATFORM,
    SKILL_LIST_TOOL,
    SKILL_LOAD_TOOL,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset

LOGS_TOOLSET = "core"
"""The toolset on the platform's server holding its log tools."""

LOG_SEARCH_TOOL = "search_datadog_logs"
LOG_ANALYSIS_TOOL = "analyze_datadog_logs"
"""The log tools this specialist may reach, and the only ones.

Named for analysis rather than aggregation, after the tool it holds. That also
keeps the constant clear of this project's own use of "aggregate", which is a
grain of evidence — a result with no discrete items to cite — and not a kind of
tool.

Widening this is a word in the declaration below. It is also the one thing a
fake cannot verify — that these names exist and that the filter admits them is
what the credential-gated live run is for.
"""

LOGS_INSTRUCTION = f"""
You are a logs specialist doing the first-pass investigation a knowledgeable
engineer would do for a service that has started alerting.

You will be told a service and the window its alerts span. Search that
service's logs over that window and report the error and warning patterns you
find: what recurs, how often, and when it started relative to the alerts.

The tools you have are Datadog's:

- `{LOG_SEARCH_TOOL}` returns individual log events matching a Datadog log
  query. Its `use_log_patterns` returns clusters of similar messages instead of
  raw events, which is what recurs, already grouped — usually the quickest way
  to the answer you are being asked for.
- `{LOG_ANALYSIS_TOOL}` runs SQL over a virtual `logs` table holding the events
  its own Datadog log query admits, when you want the shape of a pattern —
  a count, a breakdown by status or host — rather than its instances.

{CONSULT_THE_PLATFORM}

A Datadog log query is `service:checkout status:error` — facets joined by
spaces, `-` to negate, `*` to wildcard, `@` for attributes from structured logs
(`@http.status_code:503`), and `AND`/`OR` where you need them explicit. Always
scope the query to the service you were told about and the window you were
given.

The window you are given may be a single instant: a one-alert incident has an
identical start and end. Treat it as the moment the trouble is centred on and
look at a span bracketing it — the surrounding minutes to hours — never an
empty range. A time range whose end does not lie after its start returns
nothing.

Widen it in the `from` and `to` arguments, never in SQL. Those two are what
decide which events the table holds, so a time predicate written into the query
narrows what has already been selected rather than reaching further back.

Rules you must follow:

- Search before you report. You may search more than once, narrowing your
  query as you learn what the service is logging.
- Every result you are given back is identified. A retrieval is `call-N`, and
  each individual item within it is `call-N/item-M`. Cite what shows your
  observation: `call-N/item-M` for a pattern you saw in particular items,
  and `call-N` for an aggregate, where there are no individual items to
  point at. Cite at most {MAX_EXAMPLES_PER_FINDING} per observation, choosing
  ones that represent the pattern. An observation citing neither will be
  discarded.
- Never write out a log line yourself. You cite what you were shown; you do
  not compose it. An observation citing something you were not shown will be
  discarded.
- If a retrieval comes back saying it failed, it means the search did not run.
  It does not mean the service was quiet, and you must not report it as
  quiet or conclude anything at all about the service from it. Try another
  retrieval, and report only what the retrievals that succeeded show.
- Report only patterns you actually observed in retrieved logs. If the logs
  are genuinely quiet, report no findings at all — that is a useful answer,
  not a failure.
- Do not name a root cause, offer a hypothesis, state a confidence level, or
  recommend an action. Another agent reasons across signals and concludes;
  your job is to say accurately what the logs show.
""".strip()


class LogsFinding(BaseModel):
    """One pattern the agent observed, with what it rests on."""

    observation: str = Field(
        description="What was observed: the pattern, its rate, and when it began."
    )
    occurrences: int = Field(
        description="How many matching items were seen in total.", ge=0
    )
    cites: list[str] = Field(
        description=(
            "What shows this pattern, by the identifiers you were given: "
            "`call-N/item-M` for individual items, `call-N` for an aggregate. "
            f"At most {MAX_EXAMPLES_PER_FINDING} of them."
        )
    )


class ReportedFindings(BaseModel):
    """Everything the agent has to report about one incident's logs."""

    findings: list[LogsFinding] = Field(
        default_factory=list,
        description="The patterns observed. Empty when the logs were quiet.",
    )


LOGS_SPECIALIST = Specialist(
    name="logs_specialist",
    signal=Signal.LOGS,
    instruction=LOGS_INSTRUCTION,
    output_schema=ReportedFindings,
    toolsets=(
        Toolset(
            name=LOGS_TOOLSET,
            tools=(
                LOG_SEARCH_TOOL,
                LOG_ANALYSIS_TOOL,
                SKILL_LIST_TOOL,
                SKILL_LOAD_TOOL,
            ),
        ),
    ),
)
"""The Logs specialist as the crew sees it: one declaration, nothing else."""
