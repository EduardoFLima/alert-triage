"""The trace specialist, declared: its tools, its instruction, and its schema.

Two tools and one order between them: spans are searched to find a request
worth looking at, and a trace is fetched by the identifier that search
returned. Stating that order in the instruction is what stops the specialist
asking for a trace it has no identifier for.

This is the specialist whose signal a model can fake most convincingly. A
plausible account of where a slow request spends its time can be written
without retrieving anything, and would be indistinguishable from a finding to
everyone downstream. So the instruction says in as many words that a typical
request is not a finding, and the schema — like every specialist's — offers
nowhere to write a waterfall into.
"""

from pydantic import BaseModel, Field

from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset

TRACE_TOOLSET = "core"
"""The toolset on the platform's server holding its trace tools."""

SPAN_SEARCH_TOOL = "search_datadog_spans"
TRACE_TOOL = "get_datadog_trace"
"""The trace tools this specialist may reach, and the only ones."""

TRACE_INSTRUCTION = f"""
You are a trace specialist doing the first-pass investigation a knowledgeable
engineer would do for a service that has started alerting.

You will be told a service and the window its alerts span. Find the requests
to that service that were slow or that failed during that window, and report
where their time went or where they broke: which operation dominated, and what
it was waiting on.

The tools you have are Datadog's:

- `{SPAN_SEARCH_TOOL}` returns spans matching a query, which is how you find a
  request worth looking at and the identifier of the trace it belongs to.
- `{TRACE_TOOL}` returns one whole trace by its identifier, which is where you
  see what a single request actually spent its time on.

Search before you fetch: a trace is fetched by an identifier, and the search is
where an identifier comes from. A span query is facets joined by spaces —
`service:checkout status:error`, `service:checkout @duration:>2s` for the slow
ones, `-` to negate and `*` to wildcard. Always scope the query to the service
you were told about and the window you were given.

What to report:

- Which operation dominated a slow request's time, and what it was waiting on,
  read from the trace you retrieved.
- Where a failing request broke: the operation that errored and what the error
  said, read from the trace you retrieved.
- If nothing slow or failing could be retrieved for the window, report no
  findings at all. That is a useful answer.

Rules you must follow:

- Report about requests you actually retrieved. An account of how a request of
  this kind would typically behave is not a finding, however plausible it is,
  and reporting one as though it were retrieved is the worst thing you can do
  here.
- Every result you are given back is identified. A retrieval is `call-N`, and
  each individual entry within it is `call-N/item-M`. Cite what shows your
  observation: `call-N/item-M` for individual spans you read it from, and
  `call-N` for a whole trace, where there are no individual entries to point
  at. Cite at most {MAX_EXAMPLES_PER_FINDING} per observation, choosing ones
  that represent what you observed. An observation citing neither will be
  discarded.
- Never write out a span, a duration or an error message yourself. You cite
  what you were shown; you do not compose it. An observation citing something
  you were not shown will be discarded.
- If a retrieval comes back saying it failed, it means the retrieval did not
  run. It does not mean the service was fast or healthy, and you must not
  conclude anything at all about the service from it. Try another retrieval,
  and report only what the retrievals that succeeded show.
- Do not name a root cause, offer a hypothesis, state a confidence level, or
  recommend an action. Another agent reasons across signals and concludes;
  your job is to say accurately what the traces show.
""".strip()


class TraceFinding(BaseModel):
    """One thing the agent observed in a retrieved request, with what it rests on."""

    observation: str = Field(
        description=(
            "What was observed: which operation dominated the request's time or "
            "where it broke, and how that compares across the requests retrieved."
        )
    )
    occurrences: int = Field(description="How many retrieved requests show it.", ge=0)
    cites: list[str] = Field(
        description=(
            "What shows this observation, by the identifiers you were given: "
            "`call-N/item-M` for individual spans, `call-N` for a whole trace. "
            f"At most {MAX_EXAMPLES_PER_FINDING} of them."
        )
    )


class ReportedFindings(BaseModel):
    """Everything the agent has to report about one incident's requests."""

    findings: list[TraceFinding] = Field(
        default_factory=list,
        description=(
            "What was observed. Empty when nothing slow or failing was retrieved."
        ),
    )


TRACE_SPECIALIST = Specialist(
    name="trace_specialist",
    signal=Signal.TRACE,
    instruction=TRACE_INSTRUCTION,
    output_schema=ReportedFindings,
    toolsets=(Toolset(name=TRACE_TOOLSET, tools=(SPAN_SEARCH_TOOL, TRACE_TOOL)),),
)
"""The trace specialist as the crew sees it: one declaration, nothing else."""
