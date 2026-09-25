"""The trace specialist, declared: its tools, its instruction, and its schema.

An order between its tools: spans are searched to find a request worth looking
at, and a trace is fetched by the identifier that search returned. Stating the
order in the instruction is what stops the specialist asking for a trace it has
no identifier for.

Where the account has Datadog's Preview ``apm`` toolset, a third step follows:
the spans within that trace are ranked rather than read. "Which operation
dominated" is a question about ordering a trace's spans by the time they own,
and answering it by reading a whole waterfall is both unreliable on a deep
trace and expensive in context. Without Preview the specialist reads the
waterfall, which is what it has always done and is the one thing ``core`` can
still offer here.

This is the specialist whose signal a model can fake most convincingly. A
plausible account of where a slow request spends its time can be written
without retrieving anything, and would be indistinguishable from a finding to
everyone downstream. So the instruction says in as many words that a typical
request is not a finding, and the schema — like every specialist's — offers
nowhere to write a waterfall into.

Its quieter failure is the opposite one: a span query filtering on a facet the
service does not carry returns nothing, which reads exactly like a service with
nothing slow. So it is told not to guess a facet whether or not it has the
Preview tool that makes checking one cheap.
"""

from pydantic import BaseModel, Field

from alert_triage.investigation.adapters.datadog.dialect import (
    AN_EMPTY_ANSWER,
)
from alert_triage.investigation.adapters.datadog.preview import (
    APM_TOOLSET_AVAILABLE,
)
from alert_triage.investigation.adapters.datadog.tools import (
    DISCOVER_SPAN_TAGS,
    GET_TRACE,
    QUERY_TRACE,
    SEARCH_SPANS,
    DatadogTool,
    described,
    toolsets,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal
from alert_triage.investigation.domain.specialist import Specialist

_TRACE_TOOLS = (SEARCH_SPANS, GET_TRACE)
"""The trace tools every account has, whatever its Preview access."""

_PREVIEW_TOOLS = (DISCOVER_SPAN_TAGS, QUERY_TRACE)
"""Asking which facets a service's spans carry, and ranking within a trace.

Both exist only in the Preview toolset. The first is what makes a guessed
facet cheap to check; without it the specialist is still told not to guess,
and checks against the spans it has seen instead.
"""

_INSTRUCTION_TEMPLATE = """\
You are a trace specialist doing the first-pass investigation a knowledgeable
engineer would do for a service that has started alerting.

You will be told a service and the window its alerts span. Find the requests
to that service that were slow or that failed during that window, and report
where their time went or where they broke: which operation dominated, and what
it was waiting on.

The tools you have are Datadog's:

{TOOLS}

{ORDERING}

A span query is facets joined by spaces —
`service:checkout status:error`, `service:checkout @duration:>2s` for the slow
ones, `-` to negate and `*` to wildcard. Always scope the query to the service
you were told about and the window you were given.

{AN_EMPTY_ANSWER}

A span search that returns nothing may be telling you about your query rather
than about the service. Do not guess a facet.
{FACET_CHECK}

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
"""


_ORDER_WITH_RANKING = """
Search before you fetch, and rank before you conclude. A trace is fetched by an
identifier and the search is where an identifier comes from; once you hold a
trace, rank its spans rather than reading it end to end, so that which
operation dominated is something the platform told you rather than something
you judged by eye.""".strip("\n")

_ORDER_WITHOUT_RANKING = """
Search before you fetch: a trace is fetched by an identifier, and the search is
where an identifier comes from. Read the trace you fetch carefully — which
operation dominated is something you have to work out from the spans in it, so
account for where the time went rather than naming the first slow thing you
see.""".strip("\n")


_FACETS_DISCOVERED = f"""
Filter on the service, the status and the duration, which every span carries,
and ask `{DISCOVER_SPAN_TAGS.name}` which tags the service's spans carry before you
filter on any other.""".strip("\n")

_FACETS_SEEN_ON_A_SPAN = """
Filter on the service, the status and the duration, which every span carries,
and on any other attribute only once you have seen it on a span this service
returned.""".strip("\n")


def _tools(preview: bool) -> tuple[DatadogTool, ...]:
    """The tools this specialist may call, given what the account may reach."""
    return (*_TRACE_TOOLS, *(_PREVIEW_TOOLS if preview else ()))


def _instruction(preview: bool) -> str:
    """What this specialist is asked, given whether it can rank within a trace."""
    return _INSTRUCTION_TEMPLATE.format(
        TOOLS=described(*_tools(preview)),
        AN_EMPTY_ANSWER=AN_EMPTY_ANSWER,
        MAX_EXAMPLES_PER_FINDING=MAX_EXAMPLES_PER_FINDING,
        ORDERING=_ORDER_WITH_RANKING if preview else _ORDER_WITHOUT_RANKING,
        FACET_CHECK=_FACETS_DISCOVERED if preview else _FACETS_SEEN_ON_A_SPAN,
    ).strip()


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


def trace_specialist(*, preview: bool) -> Specialist:
    """Declare the trace specialist for an account with or without Preview access.

    Args:
        preview: Whether the account may reach the ``apm`` toolset, and so may
            rank a trace's spans rather than reading the waterfall.

    Returns:
        The declaration, reaching only tools the account can actually call and
        instructed only in what those tools can establish.
    """
    return Specialist(
        name="trace_specialist",
        signal=Signal.TRACE,
        instruction=_instruction(preview),
        output_schema=ReportedFindings,
        toolsets=toolsets(*_tools(preview)),
    )


TRACE_SPECIALIST = trace_specialist(preview=APM_TOOLSET_AVAILABLE)
"""The trace specialist as the crew sees it: one declaration, nothing else."""

TRACE_INSTRUCTION = TRACE_SPECIALIST.instruction
"""What the specialist is asked, for the access this deployment actually has."""
