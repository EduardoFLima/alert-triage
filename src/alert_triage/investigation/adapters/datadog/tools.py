"""Datadog's tools, each stated once: its name, its toolset, and what it does.

A tool's facts belong to the platform rather than to whichever specialist
reaches it. Two specialists sharing a tool used to declare it twice and
describe it twice in nearly the same words, and nothing but a test kept either
copy honest. Here a specialist picks tools; the toolsets it asks the server for
and the list its instruction describes are both derived from what it picked,
so the two cannot disagree.

A description says what the tool does and is true for every caller. How a
particular specialist should use it — what to ask it for, what to narrow it by
— stays in that specialist's instruction, beside the list rendered from here.
"""

import textwrap
from dataclasses import dataclass

from alert_triage.investigation.adapters.datadog.mcp import DATADOG
from alert_triage.investigation.domain.specialist import Toolset


@dataclass(frozen=True)
class DatadogTool:
    """One tool on Datadog's server.

    Attributes:
        name: What the server calls it, which is a string that either exists
            there or does not. Only the credential-gated live run settles which.
        toolset: The group the server serves it in.
        description: What it does, as a clause following its name in an
            instruction's list of tools.
    """

    name: str
    toolset: str
    description: str

    def __post_init__(self) -> None:
        """Reject a tool that could not be permitted, asked for, or told about."""
        for field in ("name", "toolset", "description"):
            if not getattr(self, field).strip():
                raise ValueError(f"A Datadog tool needs a {field}")


CORE = "core"
KUBERNETES = "kubernetes"
APM = "apm"
"""The groups the server serves its tools in, each asked for separately.

``apm`` is in Preview, and reached only where the account has it; which
specialists reach for it is decided in ``preview``, not here.
"""

LIST_SKILLS = DatadogTool(
    name="list_datadog_skills",
    toolset=CORE,
    description="lists the guides this platform publishes.",
)
LOAD_SKILL = DatadogTool(
    name="load_datadog_skill",
    toolset=CORE,
    description="loads one guide, by the name the listing gave it.",
)
"""How the platform publishes the grammars its own tools are queried in.

Every specialist that queries anything reaches both. They are rendered where
the crew is told to consult the platform, in ``dialect``, rather than in each
specialist's own list of tools.
"""

SEARCH_LOGS = DatadogTool(
    name="search_datadog_logs",
    toolset=CORE,
    description=(
        "returns individual log events matching a Datadog log query. Its "
        "`use_log_patterns` returns clusters of similar messages instead of raw "
        "events, which is what recurs, already grouped."
    ),
)
ANALYZE_LOGS = DatadogTool(
    name="analyze_datadog_logs",
    toolset=CORE,
    description=(
        "runs SQL over a virtual `logs` table holding the events its own Datadog "
        "log query admits, when you want the shape of a pattern — a count, a "
        "breakdown by status or host — rather than its instances."
    ),
)

GET_METRIC = DatadogTool(
    name="get_datadog_metric",
    toolset=CORE,
    description="returns a metric's values over a time range.",
)
SEARCH_METRICS = DatadogTool(
    name="search_datadog_metrics",
    toolset=CORE,
    description=(
        "lists the metrics that exist, filtered by name or by tag — "
        "`service:the-service` is how you narrow it to one service's."
    ),
)
"""What keeps a guessed metric name from reading as a healthy service.

A metric query naming something the platform has never heard of comes back
empty, and an empty answer is deliberately not a failure — so without a way to
ask which metrics a service reports, "this service is fine" and "that name was
made up" read the same.
"""
GET_METRIC_CONTEXT = DatadogTool(
    name="get_datadog_metric_context",
    toolset=CORE,
    description=(
        "takes one metric you have already found and tells you its unit, its "
        "type and what tags it carries."
    ),
)
"""The second half of a metric search, and not a listing of its own.

It takes one metric name and enumerates nothing. Described as though it
listed a service's metrics, it is asked for exactly that — which it has no
argument for, so the retrieval is refused.
"""
SEARCH_HOSTS = DatadogTool(
    name="search_datadog_hosts",
    toolset=CORE,
    description=(
        "finds the hosts a service runs on, with the tags that say what they are."
    ),
)

SEARCH_ENTITIES = DatadogTool(
    name="search_datadog_entities",
    toolset=CORE,
    description="searches the platform's catalogue of services.",
)
"""The catalogue search, answering about a service's identity, ownership and neighbours.

It replaced a dependency lookup that took a service and named what it talked
to. A search has to be asked a question, so whoever reaches it says what to ask.
"""
SEARCH_EVENTS = DatadogTool(
    name="search_datadog_events",
    toolset=CORE,
    description=(
        "returns the events recorded around a service — deployments, "
        "infrastructure changes and monitor alerts — which is how you find out "
        "whether something landed near the alerts."
    ),
)

SEARCH_SPANS = DatadogTool(
    name="search_datadog_spans",
    toolset=CORE,
    description=(
        "returns spans matching a query, which is how you find a request worth "
        "looking at and the identifier of the trace it belongs to."
    ),
)
GET_TRACE = DatadogTool(
    name="get_datadog_trace",
    toolset=CORE,
    description=(
        "returns one whole trace by its identifier, which is where you see what a "
        "single request actually spent its time on."
    ),
)

SEARCH_K8S_RESOURCES = DatadogTool(
    name="search_datadog_k8s_resources",
    toolset=KUBERNETES,
    description=(
        "finds the container workloads a service runs as, where the deployment "
        "has them."
    ),
)
DESCRIBE_K8S_RESOURCE = DatadogTool(
    name="describe_datadog_k8s_resource",
    toolset=KUBERNETES,
    description=(
        "returns one container workload in full, including its restarts and why "
        "it was last rescheduled."
    ),
)
ANALYSE_K8S_ROLLOUT = DatadogTool(
    name="analyse_datadog_k8s_rollout",
    toolset=KUBERNETES,
    description=(
        "accounts for how one container workload was most recently rolled out: "
        "when it started, and how it went."
    ),
)
"""Spelled ``analyse`` where its neighbours are spelled ``analyze``.

It is a string that either exists on the server or does not, and the live run
is what settles which; do not correct it by eye.
"""

LATENCY_BOTTLENECK_SUMMARY = DatadogTool(
    name="apm_latency_bottleneck_summary",
    toolset=APM,
    description=(
        "breaks a service's latency down into where the time was spent, when you "
        "have seen latency move and want to say where it went."
    ),
)
SEARCH_WATCHDOG_STORIES = DatadogTool(
    name="apm_search_watchdog_stories",
    toolset=APM,
    description=(
        "returns the anomalies the platform itself already detected for a "
        "service over a time range."
    ),
)
GET_CHANGE_STORIES = DatadogTool(
    name="get_change_stories",
    toolset=APM,
    description=(
        "returns the deployments, feature-flag changes and configuration changes "
        "recorded for a service over a time range."
    ),
)
SEARCH_CHANGE_STORIES = DatadogTool(
    name="semantic_search_change_stories",
    toolset=APM,
    description=(
        "searches the changes recorded for a service in plain language, for when "
        "you want the ones that could plausibly explain a movement you have "
        "already observed rather than all of them."
    ),
)
DISCOVER_SPAN_TAGS = DatadogTool(
    name="apm_discover_span_tags",
    toolset=APM,
    description=(
        "lists the tags a service's spans actually carry, which is how you know a "
        "facet exists before you filter on it."
    ),
)
QUERY_TRACE = DatadogTool(
    name="apm_query_trace",
    toolset=APM,
    description=(
        "filters, aggregates and ranks the spans within a trace, which is how you "
        "find the operation that dominated it rather than reading the whole "
        "waterfall yourself."
    ),
)

EVERY_TOOL = (
    LIST_SKILLS,
    LOAD_SKILL,
    SEARCH_LOGS,
    ANALYZE_LOGS,
    GET_METRIC,
    SEARCH_METRICS,
    GET_METRIC_CONTEXT,
    SEARCH_HOSTS,
    SEARCH_ENTITIES,
    SEARCH_EVENTS,
    SEARCH_SPANS,
    GET_TRACE,
    SEARCH_K8S_RESOURCES,
    DESCRIBE_K8S_RESOURCE,
    ANALYSE_K8S_ROLLOUT,
    LATENCY_BOTTLENECK_SUMMARY,
    SEARCH_WATCHDOG_STORIES,
    GET_CHANGE_STORIES,
    SEARCH_CHANGE_STORIES,
    DISCOVER_SPAN_TAGS,
    QUERY_TRACE,
)
"""The whole catalogue: only tools some specialist permits, and each once."""

WIDTH = 79
"""How wide a rendered line runs, matching the instructions written by hand."""


def toolsets(*tools: DatadogTool) -> tuple[Toolset, ...]:
    """The toolsets a specialist asks the server for, derived from the tools it picked.

    Args:
        tools: What the specialist may call, in the order it names them.

    Returns:
        One toolset per group the tools are served in, in the order each group
        was first reached, each holding its tools in the order they were picked.
    """
    grouped: dict[str, list[str]] = {}
    for tool in tools:
        grouped.setdefault(tool.toolset, []).append(tool.name)
    return tuple(
        Toolset(provider=DATADOG, name=toolset, tools=tuple(names))
        for toolset, names in grouped.items()
    )


def described(*tools: DatadogTool) -> str:
    """The list of tools an instruction tells a specialist it has.

    Hyphens are not break points: a quoted tag such as `service:the-service`
    split across lines is read by the model as two things, neither of them a
    tag.

    Args:
        tools: The tools to describe, in the order the instruction lists them.

    Returns:
        One bullet per tool, its name quoted and followed by what it does,
        wrapped under its bullet.
    """
    return "\n".join(
        textwrap.fill(
            f"- `{tool.name}` {tool.description}",
            width=WIDTH,
            subsequent_indent="  ",
            break_long_words=False,
            break_on_hyphens=False,
        )
        for tool in tools
    )
