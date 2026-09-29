"""A tool's platform facts live once, while specialist usage stays with the crew."""

import textwrap
from dataclasses import dataclass

from alert_triage.investigation.adapters.datadog.mcp import DATADOG
from alert_triage.investigation.domain.specialist import Toolset


@dataclass(frozen=True)
class DatadogTool:
    name: str
    toolset: str
    description: str

    def __post_init__(self) -> None:
        for field in ("name", "toolset", "description"):
            if not getattr(self, field).strip():
                raise ValueError(f"A Datadog tool needs a {field}")


CORE = "core"
KUBERNETES = "kubernetes"
APM = "apm"
"""Preview access is decided in ``preview`` before a specialist asks for ``apm``."""

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
"""Guide tools run at startup and are kept out of the crew's catalogue."""

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
"""A metric query for a made-up name and a quiet real metric both return empty."""
GET_METRIC_CONTEXT = DatadogTool(
    name="get_datadog_metric_context",
    toolset=CORE,
    description=(
        "takes one metric you have already found and tells you its unit, its "
        "type and what tags it carries."
    ),
)
"""It takes one metric name; describing it as a listing makes calls fail."""
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
"""The server spells this one ``analyse``; do not normalize it by eye."""

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

WIDTH = 79


def toolsets(*tools: DatadogTool) -> tuple[Toolset, ...]:
    grouped: dict[str, list[str]] = {}
    for tool in tools:
        grouped.setdefault(tool.toolset, []).append(tool.name)
    return tuple(
        Toolset(provider=DATADOG, name=toolset, tools=tuple(names))
        for toolset, names in grouped.items()
    )


def described(*tools: DatadogTool) -> str:
    """Do not split hyphenated tags; the model reads the pieces as separate tags."""
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
