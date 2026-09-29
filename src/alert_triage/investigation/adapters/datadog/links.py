"""Datadog evidence links are routed by the tool that produced the retrieval.

Only templates confirmed against a real account are built; a plausible wrong
template opens an empty page that looks like evidence.
"""

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

from alert_triage.investigation.adapters.datadog import tools
from alert_triage.investigation.contract import Section
from alert_triage.shared.window import Window

LOG_EXPLORER_PATH = "logs"

LOG_TOOLS = frozenset({tools.SEARCH_LOGS.name, tools.ANALYZE_LOGS.name})

APM_SERVICE_TOOLS = frozenset(
    tool.name
    for tool in (
        tools.GET_METRIC,
        tools.SEARCH_METRICS,
        tools.GET_METRIC_CONTEXT,
        tools.SEARCH_ENTITIES,
    )
)

TRACE_TOOLS = frozenset({tools.SEARCH_SPANS.name, tools.GET_TRACE.name})

INFRASTRUCTURE_TOOLS = frozenset(
    tool.name
    for tool in (
        tools.SEARCH_HOSTS,
        tools.SEARCH_K8S_RESOURCES,
        tools.DESCRIBE_K8S_RESOURCE,
    )
)

EVENT_TOOLS = frozenset({tools.SEARCH_EVENTS.name})
"""Repeated from triage because Datadog routes are platform knowledge."""

ADDRESSED = (
    LOG_TOOLS | APM_SERVICE_TOOLS | TRACE_TOOLS | INFRASTRUCTURE_TOOLS | EVENT_TOOLS
)

UNADDRESSED = frozenset(
    tool.name
    for tool in (
        tools.ANALYSE_K8S_ROLLOUT,
        tools.LATENCY_BOTTLENECK_SUMMARY,
        tools.SEARCH_WATCHDOG_STORIES,
        tools.GET_CHANGE_STORIES,
        tools.SEARCH_CHANGE_STORIES,
        tools.QUERY_TRACE,
        tools.DISCOVER_SPAN_TAGS,
    )
)
"""Recorded explicitly so a newly permitted tool must choose addressed or linkless."""

ITEM_KEYS = ("id", "log_id", "event_id")
"""Incomplete live-payload knowledge costs precision, not a working link."""

QUERY_KEYS = ("query", "filter_query", "search_query")

SERVICE_PAGE_ANCHORS: Mapping[Section, str] = {
    Section.ERRORS: "errors",
    Section.DEPLOYMENTS: "deployments",
    Section.DEPENDENCIES: "dependencies",
    Section.INFRASTRUCTURE: "infrastructure",
    Section.TRACES: "traces",
    Section.LOGS: "logs",
}
"""Browser-only anchors degrade to the right page if Datadog changes one."""

SERVICE_TAG_PREFIX = "service:"

ENV_TAG_PREFIX = "env:"

ENV_PARAMETER = "env"

FROM_KEYS = ("from", "from_ts", "start", "filter_from")
TO_KEYS = ("to", "to_ts", "end", "filter_to")

SECONDS_CEILING = 1e11
"""No supported Datadog window lands between seconds and milliseconds here."""


class DatadogLinks:
    def __init__(self, web_host: str) -> None:
        self._web_host = web_host

        self._service_templates: Mapping[
            str, Callable[[Mapping[str, Any], str, str | None], str]
        ] = {
            **dict.fromkeys(APM_SERVICE_TOOLS, self._service_page),
            **dict.fromkeys(TRACE_TOOLS, self._trace_explorer),
            **dict.fromkeys(INFRASTRUCTURE_TOOLS, self._infrastructure),
            **dict.fromkeys(EVENT_TOOLS, self._event_explorer),
        }

    def to_retrieval(
        self,
        tool: str,
        args: Mapping[str, Any],
        service: str = "",
        env: str | None = None,
    ) -> str | None:
        if tool in LOG_TOOLS:
            return self._log_search(args)
        template = self._service_templates.get(tool)
        if template is None or not service.strip():
            return None
        return template(args, service, env)

    def _log_search(self, args: Mapping[str, Any]) -> str:
        """Log Explorer speaks back the retrieval query, not the target service."""
        parameters: dict[str, str] = {"query": _first(args, QUERY_KEYS) or ""}
        window = _window(args)
        if window is not None:
            parameters["from_ts"], parameters["to_ts"] = window
        parameters["live"] = "false"
        return f"https://{self._web_host}/{LOG_EXPLORER_PATH}?{urlencode(parameters)}"

    def to_service(
        self,
        service: str,
        window: Window,
        section: Section | None,
        env: str | None = None,
    ) -> str | None:
        if not service.strip():
            return None
        page = self._apm_entity(
            service,
            env,
            {"start": _epoch_ms(window.start), "end": _epoch_ms(window.end)},
        )
        return page if section is None else f"{page}#{SERVICE_PAGE_ANCHORS[section]}"

    def _service_page(
        self, args: Mapping[str, Any], service: str, env: str | None
    ) -> str:
        return self._apm_entity(service, env, _apm_window(args))

    def _apm_entity(
        self, service: str, env: str | None, window: Mapping[str, str]
    ) -> str:
        page = (
            f"https://{self._web_host}/apm/entity/service%3A{quote(service, safe='')}"
        )
        parameters = {**({ENV_PARAMETER: env} if env else {}), **window}
        return f"{page}?{urlencode(parameters)}" if parameters else page

    def _trace_explorer(
        self, args: Mapping[str, Any], service: str, env: str | None
    ) -> str:
        """Trace Explorer span queries resolve differently, so scope by service."""
        parameters = {"query": _explorer_scope(service, env), **_apm_window(args)}
        return f"https://{self._web_host}/apm/traces?{urlencode(parameters)}"

    def _infrastructure(
        self, args: Mapping[str, Any], service: str, env: str | None
    ) -> str:
        """The inventory is a live view, not a windowed retrieval."""
        scope = urlencode({"filter": f"{SERVICE_TAG_PREFIX}{service}"})
        return f"https://{self._web_host}/infrastructure?{scope}"

    def _event_explorer(
        self, args: Mapping[str, Any], service: str, env: str | None
    ) -> str:
        parameters: dict[str, str] = {"query": _explorer_scope(service, env)}
        window = _window(args)
        if window is not None:
            parameters["from_ts"], parameters["to_ts"] = window
        parameters["live"] = "false"
        return f"https://{self._web_host}/event/explorer?{urlencode(parameters)}"

    def to_item(
        self,
        tool: str,
        payload: Any,
        within: str | None,
        service: str = "",
        env: str | None = None,
    ) -> str | None:
        """An item without its own identifier still points to its retrieval."""
        if tool not in LOG_TOOLS:
            return within if tool in self._service_templates else None
        item = _first(payload, ITEM_KEYS) if isinstance(payload, dict) else None
        if item is None:
            return within
        search = within or self._log_search({})
        return f"{search}&{urlencode({'event': item})}"


def _explorer_scope(service: str, env: str | None) -> str:
    scope = f"{SERVICE_TAG_PREFIX}{service}"
    return f"{scope} {ENV_TAG_PREFIX}{env}" if env else scope


def _first(source: Any, keys: tuple[str, ...]) -> str | None:
    if not isinstance(source, Mapping):
        return None
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _window(args: Mapping[str, Any]) -> tuple[str, str] | None:
    """Use both ends or neither; a half-window links to the wrong evidence."""
    start = _milliseconds(_end_of(args, FROM_KEYS))
    end = _milliseconds(_end_of(args, TO_KEYS))
    if start is None or end is None:
        return None
    return str(start), str(end)


def _apm_window(args: Mapping[str, Any]) -> dict[str, str]:
    window = _window(args)
    if window is None:
        return {}
    start, end = window
    return {"start": start, "end": end}


def _epoch_ms(instant: datetime) -> str:
    return str(int(instant.timestamp() * 1000))


def _end_of(args: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = args.get(key)
        if value is not None:
            return value
    return None


def _milliseconds(value: Any) -> int | None:
    """Tool schemas vary between ISO instants and epoch values."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return _scaled(float(value))
    if not isinstance(value, str):
        return None
    try:
        return _scaled(float(value))
    except ValueError:
        pass
    try:
        return int(datetime.fromisoformat(value).timestamp() * 1000)
    except ValueError:
        return None


def _scaled(value: float) -> int:
    return int(value if value >= SECONDS_CEILING else value * 1000)
