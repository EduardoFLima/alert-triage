"""Datadog's addresses for what a retrieval returned, at both grains.

The platform half of a link. Nothing here reasons about evidence and nothing
here is reached by the framework adapter: a builder bound to a site is handed
across at composition, which is what lets a second platform's specialist bring
its own addresses without this file being edited.

What decides the destination is the tool, not the specialist that called it.
Two specialists reaching the same tool want the same page, and one specialist
reaching four tools wants four different ones — so the routing below is keyed
by tool name and a specialist added later inherits nothing by accident.

Only forms Datadog documents are built, and a tool whose product page this
project has not established is left unaddressed rather than pointed somewhere
plausible. A link to the wrong product is worse than no link: it opens, which
is exactly what stops a reader noticing it is wrong. Every retrieval used to be
addressed as a Log Explorer search, which was right while logs were all a
specialist could ask for and sent a metric query into a log search the moment
they were not.

A searchable destination carries the query and the window it ran over as
millisecond timestamps, in a view pinned to that window rather than to the
present. A plain one is the product's own page: the reader lands where the
evidence lives and asks again there. An item the payload identifies is named on
its search where the product can show one, so an address that cannot open the
item still opens the search the item is in. A link that degrades to the right
page is the whole point: the broken link this replaced degraded to nowhere.

"Item" throughout, never "entry": it is the word the citation format
``call-N/item-M`` already commits this project to, and one thing retrieved
deserves one name.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

LOG_EXPLORER_PATH = "logs"
TRACE_EXPLORER_PATH = "apm/traces"
METRIC_EXPLORER_PATH = "metric/explorer"
HOST_LIST_PATH = "infrastructure"
KUBERNETES_POD_EXPLORER_PATH = "orchestration/explorer/pod"
SERVICE_CATALOGUE_PATH = "services"
SERVICE_PAGE_PATH = "apm/entity"
"""The products a retrieval is opened in, each read from Datadog's own docs."""

SEARCHABLE_DESTINATIONS = {
    "search_datadog_logs": LOG_EXPLORER_PATH,
    "analyze_datadog_logs": LOG_EXPLORER_PATH,
    "search_datadog_spans": TRACE_EXPLORER_PATH,
    "get_datadog_trace": TRACE_EXPLORER_PATH,
}
"""Tools whose product takes the query and window the tool was called with.

Only the log form is established against a real account; the trace explorer is
the same explorer contract and is not yet confirmed to honour it. A parameter
it ignores costs a reader the pre-filled search, not the page.
"""

SERVICE_SCOPED_DESTINATIONS = {
    "search_datadog_k8s_resources": KUBERNETES_POD_EXPLORER_PATH,
    "describe_datadog_k8s_resource": KUBERNETES_POD_EXPLORER_PATH,
}
"""Tools whose product is a whole estate, narrowed to the service that alerted.

The pod explorer opened at its own root lists every pod in every cluster, which
is not evidence about anything. Scoping it is a ``service:`` term in a ``query``
parameter, so the service is read out of what the tool was called with, exactly
as the service page reads it — the two products want it in different places and
it is the same fact.
"""

SERVICE_DESTINATIONS = frozenset({"search_datadog_service_dependencies"})
"""Tools whose evidence is about one service, and opens on that service's page.

Datadog addresses a service as ``/apm/entity/service%3A<name>`` rather than by
a query on the catalogue, so the name is part of the path and has to be read
out of what the tool was called with. A retrieval that named no service falls
back to the catalogue, because a service page for no service is a 404 and the
catalogue is where a reader would look one up anyway.
"""

SERVICE_KEYS = ("service", "service_name", "serviceName", "filter_service")
"""What a tool called the service it was asked about."""

PAGE_DESTINATIONS = {
    "search_datadog_metrics": METRIC_EXPLORER_PATH,
    "get_datadog_metric": METRIC_EXPLORER_PATH,
    "get_datadog_metric_context": METRIC_EXPLORER_PATH,
    "search_datadog_hosts": HOST_LIST_PATH,
}
"""Tools whose product page is documented but whose query parameters are not.

Opened as the page itself. Pre-filling it from a query nobody has established
the syntax of is how a link arrives at a product with a filter it cannot parse.
"""

DATADOG_DESTINATIONS = (
    SEARCHABLE_DESTINATIONS
    | SERVICE_SCOPED_DESTINATIONS
    | PAGE_DESTINATIONS
    | dict.fromkeys(SERVICE_DESTINATIONS, SERVICE_PAGE_PATH)
)
"""Every tool this project can address, and where each opens."""

UNADDRESSED_TOOLS = frozenset({"search_datadog_events"})
"""Declared tools deliberately left without an address.

The Events Explorer's path is not stated in Datadog's documentation, and this
module does not guess one. Listing it here rather than omitting it is what
keeps the completeness check honest: a tool is unaddressed because somebody
decided so, never because nobody noticed.
"""

ITEM_ANCHORED_PATHS = frozenset({LOG_EXPLORER_PATH})
"""Products documented to open one named item within a search.

Anchoring an item onto a page that cannot show one produces an address that
opens on the wrong state, so everywhere else an item degrades to its retrieval.
"""

ITEM_KEYS = ("id", "log_id", "event_id")
"""Where a retrieved item's own identifier is found, where it has one.

Which of these a live payload actually uses is what the credential-gated run
answers. An item under none of them is addressed as its retrieval, which is
why the list being incomplete costs precision rather than a working link.
"""

QUERY_KEYS = ("query", "filter_query", "search_query")
"""What the tool called the log query it was given."""

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

    def to_retrieval(self, args: Mapping[str, Any], *, tool: str) -> str | None:
        """Where the retrieval one tool produced is opened.

        Args:
            args: What the tool was called with. The query and the window are
                read out of it; what cannot be read is left off rather than
                guessed.
            tool: What produced the retrieval, which is what decides the
                product it opens in.

        Returns:
            That product's address for this retrieval, or ``None`` where this
            project has established no page for the tool.
        """
        if tool in SEARCHABLE_DESTINATIONS:
            return self._searched(SEARCHABLE_DESTINATIONS[tool], args)
        service = _first(args, SERVICE_KEYS)
        if tool in SERVICE_SCOPED_DESTINATIONS:
            return self._scoped(SERVICE_SCOPED_DESTINATIONS[tool], service)
        if tool in SERVICE_DESTINATIONS:
            return self._service_page(service)
        page = PAGE_DESTINATIONS.get(tool)
        return None if page is None else f"https://{self._web_host}/{page}"

    def to_item(self, payload: Any, within: str | None, *, tool: str) -> str | None:
        """Where one retrieved item is opened.

        Args:
            payload: The item as the platform returned it.
            within: Where the retrieval it came from is opened, which is what
                an item the payload does not name falls back to.
            tool: What produced it, which is what decides whether its product
                can open one item at all.

        Returns:
            The address of that item, of the retrieval it came from, or
            ``None`` where the platform offers neither.
        """
        if within is None or not self._anchors_items(tool):
            return within
        item = _first(payload, ITEM_KEYS) if isinstance(payload, dict) else None
        if item is None:
            return within
        return f"{within}&{urlencode({'event': item})}"

    def _searched(self, path: str, args: Mapping[str, Any]) -> str:
        """One product's search, carrying the query and window it ran over."""
        parameters: dict[str, str] = {"query": _first(args, QUERY_KEYS) or ""}
        window = _window(args)
        if window is not None:
            parameters["from_ts"], parameters["to_ts"] = window
        parameters["live"] = "false"
        return f"https://{self._web_host}/{path}?{urlencode(parameters)}"

    def _scoped(self, path: str, service: str | None) -> str:
        """One product narrowed to the service that alerted, where it was named."""
        page = f"https://{self._web_host}/{path}"
        if service is None:
            return page
        return f"{page}?{urlencode({'query': f'service:{service}'})}"

    def _service_page(self, service: str | None) -> str:
        """One service's own page, or the catalogue when the tool named none."""
        if service is None:
            return f"https://{self._web_host}/{SERVICE_CATALOGUE_PATH}"
        named = quote(f"service:{service}", safe="")
        return f"https://{self._web_host}/{SERVICE_PAGE_PATH}/{named}"

    def _anchors_items(self, tool: str) -> bool:
        """Whether this tool's product is documented to open one named item."""
        return SEARCHABLE_DESTINATIONS.get(tool) in ITEM_ANCHORED_PATHS


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
