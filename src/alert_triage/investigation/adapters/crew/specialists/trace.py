from pydantic import BaseModel, Field

from alert_triage.investigation.adapters.crew.specialists.section import (
    SECTION_DESCRIPTION,
)
from alert_triage.investigation.adapters.datadog.dialect import (
    AN_EMPTY_ANSWER,
    IN_THE_ENVIRONMENT,
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
from alert_triage.investigation.contract import (
    MAX_EXAMPLES_PER_FINDING,
    Section,
    Signal,
)
from alert_triage.investigation.domain.specialist import Specialist

_TRACE_TOOLS = (SEARCH_SPANS, GET_TRACE)
_PREVIEW_TOOLS = (DISCOVER_SPAN_TAGS, QUERY_TRACE)
_INSTRUCTION_TEMPLATE = """\
You are a trace specialist doing the first-pass investigation a knowledgeable
engineer would do for a service that has started alerting.

You will be told a service, its environment, and the window its alerts span.
Find the requests to that service that were slow or that failed during that
window, and report where their time went or where they broke: which operation
dominated, and what it was waiting on.

The tools you have are Datadog's:

{TOOLS}

{ORDERING}

A span query is facets joined by spaces —
`service:checkout status:error`, `service:checkout @duration:>2s` for the slow
ones, `-` to negate and `*` to wildcard. Ask about the window you were given.

{IN_THE_ENVIRONMENT}

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
    return (*_TRACE_TOOLS, *(_PREVIEW_TOOLS if preview else ()))


def _instruction(preview: bool) -> str:
    return _INSTRUCTION_TEMPLATE.format(
        TOOLS=described(*_tools(preview)),
        AN_EMPTY_ANSWER=AN_EMPTY_ANSWER,
        IN_THE_ENVIRONMENT=IN_THE_ENVIRONMENT,
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
    section: Section | None = Field(default=None, description=SECTION_DESCRIPTION)


class ReportedFindings(BaseModel):
    """Everything the agent has to report about one incident's requests."""

    findings: list[TraceFinding] = Field(
        default_factory=list,
        description=(
            "What was observed. Empty when nothing slow or failing was retrieved."
        ),
    )


def trace_specialist(*, preview: bool) -> Specialist:
    return Specialist(
        name="trace_specialist",
        signal=Signal.TRACE,
        instruction=_instruction(preview),
        output_schema=ReportedFindings,
        toolsets=toolsets(*_tools(preview)),
    )


TRACE_SPECIALIST = trace_specialist(preview=APM_TOOLSET_AVAILABLE)
TRACE_INSTRUCTION = TRACE_SPECIALIST.instruction
