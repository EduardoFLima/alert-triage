"""Fetching alerts from Datadog's Events API and translating them to Alerts.

Everything Datadog-shaped stops here: the ``team:`` and ``service:`` tag
encodings, the cursor pagination, the SDK's exceptions and payload models. What
leaves is a list of ``Alert``.
"""

import logging
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import urlencode

from datadog_api_client import ApiClient, Configuration
from datadog_api_client.exceptions import OpenApiException
from datadog_api_client.v2.api.events_api import EventsApi
from datadog_api_client.v2.model.event_response import EventResponse
from datadog_api_client.v2.model.events_list_request import EventsListRequest
from datadog_api_client.v2.model.events_list_response import EventsListResponse
from datadog_api_client.v2.model.events_query_filter import EventsQueryFilter
from datadog_api_client.v2.model.events_request_page import EventsRequestPage
from urllib3.exceptions import HTTPError as TransportError

from alert_triage.configuration.settings import Ingestion, Scope
from alert_triage.shared import journal
from alert_triage.triage.adapters.datadog.connection import DatadogConnection
from alert_triage.triage.adapters.datadog.latency import read_latency_ms
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.ports.alert_source import AlertSourceError

SERVICE_TAG_PREFIX = "service:"

# Datadog files a monitor's firing events under this source; without it the
# search also returns deploys, comments, and everything else on the event feed.
MONITOR_ALERT_QUERY = "source:alert"

PAGE_LIMIT = 100

LINK_MARGIN = timedelta(minutes=30)
"""How much either side of a firing an alert's link shows.

A page pinned to the instant an alert fired shows a reader the moment and none
of its run-up. Half an hour each way is enough to see the shape of it without
being a window a reader has to search within.
"""

_log = logging.getLogger(__name__)


class EventSearch(Protocol):
    """The one endpoint this adapter uses, named so a test can stand in for it."""

    def search_events(self, *, body: EventsListRequest) -> EventsListResponse:
        """Search events matching the request body."""
        ...


class DatadogAlertSource:
    """An ``AlertSource`` backed by Datadog's Events API v2 search endpoint.

    The API client is injected rather than built here: constructing it needs
    credentials, which belong to the composition root, and injecting it is what
    lets the tests drive translation and pagination with no network.
    """

    def __init__(self, events: EventSearch, scope: Scope, web_host: str) -> None:
        """Bind the adapter to an endpoint, a scope, and a web host.

        Args:
            events: The Datadog events endpoint to query.
            scope: What is in scope, in the project's own terms: the owner
                whose alerts are wanted and, where it names any, the services.
            web_host: Where this account's web app is served, used to build a
                link a human can open. The whole host rather than the region:
                an organisation may be issued a sub-domain of its own, and
                composing ``app`` in here would send its readers nowhere.
        """
        self._events = events
        self._scope = scope
        self._watched = frozenset(service.name for service in scope.services)
        self._web_host = web_host

    @property
    def _owner(self) -> str:
        """The owner in scope, which is what a failure and a banner name."""
        return self._scope.owner

    def fetch_since(self, since: datetime) -> Sequence[Alert]:
        """Fetch the in-scope alerts that fired at or after ``since``."""
        _log.info(
            journal.banner(
                "FETCHING ALERTS",
                owner=self._owner,
                services=_watching(self._watched),
                since=since.isoformat(),
            )
        )

        return [
            alert
            for event in self._events_since(since)
            if (alert := self._to_alert(event)) is not None
            if self._in_scope(alert)
        ]

    def _in_scope(self, alert: Alert) -> bool:
        """Whether this alert is for a service the scope watches.

        Applied to what came back rather than left to the query: the port
        guarantees the narrowing, and a guarantee resting on a vendor's query
        grammar is one nobody can check without an account — and one that
        fails silently the day a service name carries something the grammar
        treats specially.
        """
        return not self._watched or alert.service in self._watched

    def _events_since(self, since: datetime) -> Iterator[EventResponse]:
        """Walk the cursor to exhaustion, so a caller never sees a partial result."""
        cursor: str | None = None
        while True:
            page = self._search(since, cursor)
            yield from page.data
            cursor = _next_cursor(page)
            if cursor is None:
                return

    def _search(self, since: datetime, cursor: str | None) -> EventsListResponse:
        """Fetch one page, turning any failure of it into the port's own.

        This is the boundary: past it, a caller catches ``AlertSourceError``
        and never learns that Datadog was involved. Failing here rather than
        returning what was retrieved so far is deliberate — a partial result is
        indistinguishable from a quiet period.

        Both libraries' roots are caught rather than the particular errors
        under them. The SDK reaches the platform through urllib3 but translates
        only one of its failures, so a refused connection or a spent retry
        bound arrives as a ``TransportError`` that no ``OpenApiException`` catch
        would see — and a caller would meet a failure this boundary exists to
        have hidden. Naming the leaves instead would leave the same gap open
        for whichever leaf either library adds next.

        Deliberately not ``except Exception``: a defect in the translation
        below should still crash rather than be reported as a failed fetch.
        """
        try:
            return self._events.search_events(body=self._request(since, cursor))
        except (OpenApiException, TransportError) as error:
            raise AlertSourceError(
                f"Could not fetch alerts for owner {self._owner!r} from Datadog: "
                f"{error}"
            ) from error

    def _request(self, since: datetime, cursor: str | None) -> EventsListRequest:
        """Build the search request for one page of in-scope alerts."""
        page = EventsRequestPage(limit=PAGE_LIMIT)
        if cursor is not None:
            page.cursor = cursor
        return EventsListRequest(
            filter=EventsQueryFilter(
                query=self._query(),
                _from=since.isoformat(),
                to="now",
            ),
            page=page,
        )

    def _query(self) -> str:
        """Ask Datadog for as little as it can be asked for.

        Narrowing the search to the watched services is what makes a scoped run
        cheap, and nothing more: ``_in_scope`` is what guarantees the result,
        so a name this grammar mishandles costs a wasted page rather than an
        alert nobody notices was triaged.
        """
        owned = f"{MONITOR_ALERT_QUERY} team:{self._owner}"
        if not self._watched:
            return owned
        services = " OR ".join(
            f"{SERVICE_TAG_PREFIX}{name}" for name in sorted(self._watched)
        )
        return f"{owned} ({services})"

    def _to_alert(self, event: EventResponse) -> Alert | None:
        """Translate one event, or ``None`` when it carries no service tag.

        An alert with no service cannot be grouped or reported against
        anything, so it is dropped rather than given a placeholder.
        """
        attributes = event.attributes
        service = _service_of(getattr(attributes, "tags", []))
        if service is None:
            return None
        fired_at = _as_utc(attributes.timestamp)
        return Alert(
            service=service,
            fired_at=fired_at,
            source_id=event.id,
            title=getattr(getattr(attributes, "attributes", None), "title", ""),
            link=self._link_to(attributes, service, fired_at),
            observed_latency_ms=read_latency_ms(getattr(attributes, "message", None)),
        )

    def _link_to(self, attributes: object, service: str, fired_at: datetime) -> str:
        """Where a reader opens what fired, over the period it fired in.

        The monitor that raised the alert where the event names one, and the
        service's own events where it does not. Never the event itself: the v2
        identifier this API returns has no page of its own, and a link built
        from one reads as working until a human follows it.
        """
        window = _window_around(fired_at)
        monitor = getattr(getattr(attributes, "attributes", None), "monitor_id", None)
        if monitor is not None:
            return f"https://{self._web_host}/monitors/{monitor}?{urlencode(window)}"
        if not service:
            return ""
        over_the_service = {
            "query": f"{MONITOR_ALERT_QUERY} {SERVICE_TAG_PREFIX}{service}",
            **window,
        }
        return f"https://{self._web_host}/event/explorer?{urlencode(over_the_service)}"


def build_configuration(
    connection: DatadogConnection, ingestion: Ingestion
) -> Configuration:
    """Configure the SDK client from where Datadog is and how hard to try.

    Ingestion's two bounds are mapped onto the client's own timeout and retry
    policy rather than hand-rolled around it: the SDK already backs off and
    already knows which statuses are worth retrying. The investigation circuit
    breakers are deliberately not an input here.

    Args:
        connection: Where Datadog is and how to authenticate.
        ingestion: The bounds a fetch runs under.

    Returns:
        A configuration ready to build an API client from.
    """
    configuration = Configuration(
        api_key={
            "apiKeyAuth": connection.api_key,
            "appKeyAuth": connection.app_key,
        },
        request_timeout=ingestion.request_timeout_seconds,
        enable_retry=True,
        max_retries=ingestion.max_retries,
    )
    configuration.server_variables["site"] = connection.site
    return configuration


def build_alert_source(
    connection: DatadogConnection, ingestion: Ingestion, scope: Scope
) -> DatadogAlertSource:
    """Assemble the adapter and the client it queries through.

    The composition root calls this; the adapter itself stays free of
    credentials so its tests need neither network nor monkeypatching.

    Args:
        connection: Where Datadog is and how to authenticate.
        ingestion: The bounds a fetch runs under.
        scope: What is in scope: the owner, and the services where any are
            named.

    Returns:
        An ``AlertSource`` backed by Datadog.
    """
    client = ApiClient(build_configuration(connection, ingestion))
    return DatadogAlertSource(
        events=EventsApi(client), scope=scope, web_host=connection.web_host
    )


def _watching(services: frozenset[str]) -> str:
    """Name the services a fetch is narrowed to, so a quiet run says why."""
    return ", ".join(sorted(services)) if services else "every service"


def _next_cursor(page: EventsListResponse) -> str | None:
    """Read the cursor for the page after this one; absent means this was the last."""
    meta = getattr(page, "meta", None)
    return getattr(getattr(meta, "page", None), "after", None)


def _service_of(tags: Sequence[str]) -> str | None:
    """Read the service Datadog carries as a ``service:<name>`` tag."""
    for tag in tags:
        if tag.startswith(SERVICE_TAG_PREFIX):
            return tag.removeprefix(SERVICE_TAG_PREFIX)
    return None


def _window_around(fired_at: datetime) -> dict[str, str]:
    """The period a link shows, pinned so it outlives the moment it was built."""
    return {
        "from_ts": str(int((fired_at - LINK_MARGIN).timestamp() * 1000)),
        "to_ts": str(int((fired_at + LINK_MARGIN).timestamp() * 1000)),
        "live": "false",
    }


def _as_utc(timestamp: datetime) -> datetime:
    """Express a fire time in UTC so alerts from any source compare alike."""
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
