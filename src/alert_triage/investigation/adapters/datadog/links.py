"""Datadog's addresses for what a retrieval returned, at both grains.

The platform half of a link. Nothing here reasons about evidence and nothing
here is reached by the framework adapter: a builder bound to a site is handed
across at composition, which is what lets a second platform's specialist bring
its own addresses without this file being edited.

An address is routed on the tool that produced the retrieval, because what a
retrieval came from depends on which tool was called and its arguments cannot
say: a query over a window is a log search, a metric, or an audit trail. Only
templates confirmed against a real account are built, one per kind of tool, and a
tool with no template gets no address at all. That is deliberate. An address built
for another kind of retrieval opens a page that looks like an answer — an empty
Log Explorer under a metric — and a reader cannot tell it from one that is
genuinely empty, whereas no address is visibly nothing.

Most templates are service-scoped, composed from the service the investigation
holds and the window the retrieval ran over rather than from the query in its
arguments: a metric, its context and the catalogue open the service's own APM
page; spans and traces open the Trace Explorer scoped to the service; hosts and
Kubernetes workloads open the service's infrastructure inventory; events open
the Event Explorer over the service. The Log Explorer's is the exception,
composed from the retrieval's own query — a query, the window it ran over as
millisecond timestamps, and a view pinned to that window rather than to the
present. An item the payload identifies is addressed as its retrieval with the
item named on it, so an address that cannot open the item still opens the view
the item is in. A link that degrades to the right page is the whole point.

"Item" throughout, never "entry": it is the word the citation format
``call-N/item-M`` already commits this project to, and one thing retrieved
deserves one name.
"""

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from alert_triage.investigation.adapters.datadog import tools

LOG_EXPLORER_PATH = "logs"

LOG_TOOLS = frozenset({tools.SEARCH_LOGS.name, tools.ANALYZE_LOGS.name})
"""The tools whose retrievals are Log Explorer searches, and the only ones."""

APM_SERVICE_TOOLS = frozenset(
    tool.name
    for tool in (
        tools.GET_METRIC,
        tools.SEARCH_METRICS,
        tools.GET_METRIC_CONTEXT,
        tools.SEARCH_ENTITIES,
    )
)
"""The tools a service's own APM page answers for — its metrics and its catalogue."""

TRACE_TOOLS = frozenset({tools.SEARCH_SPANS.name, tools.GET_TRACE.name})
"""The tools whose retrievals are the service's traces, opened in the explorer."""

INFRASTRUCTURE_TOOLS = frozenset(
    tool.name
    for tool in (
        tools.SEARCH_HOSTS,
        tools.SEARCH_K8S_RESOURCES,
        tools.DESCRIBE_K8S_RESOURCE,
    )
)
"""The tools whose retrievals are what a service runs on, opened in its inventory."""

EVENT_TOOLS = frozenset({tools.SEARCH_EVENTS.name})
"""The tool whose retrievals are the service's events, opened in their explorer.

Its address is the same shape ``triage`` builds for an alert's own events and is
written again here rather than shared: a Datadog route is platform knowledge one
context keeps, not vocabulary two contexts pass across the shared kernel.
"""

ADDRESSED = (
    LOG_TOOLS | APM_SERVICE_TOOLS | TRACE_TOOLS | INFRASTRUCTURE_TOOLS | EVENT_TOOLS
)
"""Every tool an address template is known for."""

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
        tools.LIST_SKILLS,
        tools.LOAD_SKILL,
    )
)
"""Every tool the crew reaches that deliberately has no address template yet.

Recorded rather than merely absent, so that a tool a specialist is widened to
later fails a unit test until someone decides which of these two it belongs
in, instead of quietly reporting its evidence without an address. A tool here
is linkless because no template for it has been confirmed against a real
account, and an unconfirmed template is how a reader gets sent to a page that
looks like an answer and is not. The skill tools are here for a different
reason: what they return is the platform's guidance on its own grammar, not
evidence of anything.
"""

ITEM_KEYS = ("id", "log_id", "event_id")
"""Where a retrieved item's own identifier is found, where it has one.

Which of these a live payload actually uses is what the credential-gated run
answers. An item under none of them is addressed as its retrieval, which is
why the list being incomplete costs precision rather than a working link.
"""

QUERY_KEYS = ("query", "filter_query", "search_query")
"""What the tool called the log query it was given."""

SERVICE_TAG_PREFIX = "service:"
"""How a service is named to an explorer's query, the same tag ``triage`` uses."""

FROM_KEYS = ("from", "from_ts", "start", "filter_from")
TO_KEYS = ("to", "to_ts", "end", "filter_to")
"""What the tool called the ends of the window it searched."""

SECONDS_CEILING = 1e11
"""Above this an epoch value is milliseconds, below it seconds.

Roughly the year 5138 in seconds and 1973 in milliseconds: no window either
tool is called with lands in the gap, so the two are told apart without asking
the caller which it meant.
"""


class DatadogLinks:
    """Where the evidence one account returned is opened, bound to its host."""

    def __init__(self, web_host: str) -> None:
        """Bind the addresses to one deployment's account.

        Args:
            web_host: Where this account's web app is served, e.g.
                ``app.datadoghq.eu``. The whole host rather than the region:
                an organisation may be issued a sub-domain of its own, and an
                account addressed on the wrong host gets a page it cannot see.
        """
        self._web_host = web_host

        self._templates: Mapping[str, Callable[[Mapping[str, Any], str], str]] = {
            **dict.fromkeys(LOG_TOOLS, self._log_search),
            **dict.fromkeys(APM_SERVICE_TOOLS, self._service_page),
            **dict.fromkeys(TRACE_TOOLS, self._trace_explorer),
            **dict.fromkeys(INFRASTRUCTURE_TOOLS, self._infrastructure),
            **dict.fromkeys(EVENT_TOOLS, self._event_explorer),
        }

    def to_retrieval(
        self, tool: str, args: Mapping[str, Any], service: str = ""
    ) -> str | None:
        """Where whatever produced one retrieval is opened.

        Args:
            tool: The tool that was called, which decides what kind of page
                the retrieval came from.
            args: What the tool was called with. What the address needs is read
                out of it; what cannot be read is left off rather than guessed.
            service: The service under investigation, which the service-scoped
                pages are addressed to. Held by the investigation rather than
                read out of ``args``, because how a service is named in a query
                differs by tool and a page scoped to the wrong one is a page to
                the wrong thing.

        Returns:
            The address of the view that retrieval came from, or ``None`` where
            no address template is known for the tool. An address built for another
            kind of retrieval opens a page that looks like an answer and is not.
        """
        template = self._templates.get(tool)
        return None if template is None else template(args, service)

    def _log_search(self, args: Mapping[str, Any], service: str) -> str:
        """The Log Explorer search a log retrieval came from, pinned to its window.

        The one template composed from the retrieval's own query rather than
        from the service, because a log search is what its query says and the
        Log Explorer speaks that query back.
        """
        parameters: dict[str, str] = {"query": _first(args, QUERY_KEYS) or ""}
        window = _window(args)
        if window is not None:
            parameters["from_ts"], parameters["to_ts"] = window
        parameters["live"] = "false"
        return f"https://{self._web_host}/{LOG_EXPLORER_PATH}?{urlencode(parameters)}"

    def _service_page(self, args: Mapping[str, Any], service: str) -> str:
        """The service's own APM page, over the window the retrieval ran across.

        Where a metric, a metric search, a metric's context and the catalogue
        all point: the entity whose resources they describe, not the query that
        described them.
        """
        page = f"https://{self._web_host}/apm/entity/service%3A{service}"
        window = _apm_window(args)
        return f"{page}?{urlencode(window)}" if window else page

    def _trace_explorer(self, args: Mapping[str, Any], service: str) -> str:
        """The Trace Explorer scoped to the service, over the retrieval's window.

        Scoped by the service and not by the retrieval's query: a span-level
        query resolves differently on a view that lists the traces containing a
        matching span, and a service scope means the same thing on either.
        """
        parameters = {"query": f"{SERVICE_TAG_PREFIX}{service}", **_apm_window(args)}
        return f"https://{self._web_host}/apm/traces?{urlencode(parameters)}"

    def _infrastructure(self, args: Mapping[str, Any], service: str) -> str:
        """The infrastructure inventory filtered to what the service runs on.

        The one service-scoped address with no window: the inventory is a live
        view of what is running now, not a period a retrieval ran over.
        """
        scope = urlencode({"filter": f"{SERVICE_TAG_PREFIX}{service}"})
        return f"https://{self._web_host}/infrastructure?{scope}"

    def _event_explorer(self, args: Mapping[str, Any], service: str) -> str:
        """The Event Explorer over the service, pinned to the retrieval's window."""
        parameters: dict[str, str] = {"query": f"{SERVICE_TAG_PREFIX}{service}"}
        window = _window(args)
        if window is not None:
            parameters["from_ts"], parameters["to_ts"] = window
        parameters["live"] = "false"
        return f"https://{self._web_host}/event/explorer?{urlencode(parameters)}"

    def to_item(
        self, tool: str, payload: Any, within: str | None, service: str = ""
    ) -> str | None:
        """Where one retrieved item is opened.

        Args:
            tool: The tool whose retrieval the item came from. An item from a
                tool no address template is known for gets none, rather than one
                inherited from a kind of retrieval it did not come from.
            payload: The item as the platform returned it.
            within: Where the retrieval it came from is opened, which is what
                an item the payload does not identify falls back to.
            service: The service under investigation, used to rebuild the
                retrieval's address where the caller did not supply one.

        Returns:
            The address of that item, of the retrieval it came from, or
            ``None`` where the platform offers neither.
        """
        template = self._templates.get(tool)
        if template is None:
            return None
        item = _first(payload, ITEM_KEYS) if isinstance(payload, dict) else None
        if item is None:
            return within
        search = within or template({}, service)
        return f"{search}&{urlencode({'event': item})}"


def _first(source: Any, keys: tuple[str, ...]) -> str | None:
    """The first of these keys the source carries a usable value under."""
    if not isinstance(source, Mapping):
        return None
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _window(args: Mapping[str, Any]) -> tuple[str, str] | None:
    """The window a retrieval ran over, as the explorer expresses one.

    Both ends or neither: an address carrying one end of a window shows a
    reader a period the evidence was not gathered over, which is a link to the
    wrong thing rather than a link to less.
    """
    start = _milliseconds(_end_of(args, FROM_KEYS))
    end = _milliseconds(_end_of(args, TO_KEYS))
    if start is None or end is None:
        return None
    return str(start), str(end)


def _apm_window(args: Mapping[str, Any]) -> dict[str, str]:
    """A retrieval's window under the parameter names an APM view expresses it by.

    Empty where the window cannot be read, so an APM address drops both ends
    rather than one, for the reason ``_window`` already refuses a half window.
    """
    window = _window(args)
    if window is None:
        return {}
    start, end = window
    return {"start": start, "end": end}


def _end_of(args: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    """What the tool was told one end of its window was, under any of its names."""
    for key in keys:
        value = args.get(key)
        if value is not None:
            return value
    return None


def _milliseconds(value: Any) -> int | None:
    """One end of a window as the explorer expresses it, or ``None`` if unreadable.

    A model calls a tool with what the tool's own schema asks for, which is an
    instant in some accounts and an epoch in others. A value that is neither is
    left to the caller to drop.
    """
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
    """An epoch value in whichever unit it was given, expressed in milliseconds."""
    return int(value if value >= SECONDS_CEILING else value * 1000)
