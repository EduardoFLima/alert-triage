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

from alert_triage.configuration.settings import Ingestion
from alert_triage.shared import journal
from alert_triage.triage.adapters.datadog.connection import DatadogConnection
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.ports.alert_source import AlertSourceError

SERVICE_TAG_PREFIX = "service:"
OWNER_TAG_PREFIX = "team:"
ENV_TAG_PREFIX = "env:"

# Datadog files a monitor's firing events under this source; without it the
# search also returns deploys, comments, and everything else on the event feed.
MONITOR_ALERT_QUERY = "source:alert"

PAGE_LIMIT = 100

LINK_MARGIN = timedelta(minutes=30)

_log = logging.getLogger(__name__)


class EventSearch(Protocol):
    def search_events(self, *, body: EventsListRequest) -> EventsListResponse: ...


class DatadogAlertSource:
    """The API client is injected so translation and pagination test without network."""

    def __init__(
        self,
        events: EventSearch,
        owner: str | None = None,
        web_host: str = "",
        services: Sequence[str] = (),
        *,
        env: str,
    ) -> None:
        self._events = events
        self._owner = owner
        self._web_host = web_host
        self._services = tuple(services)
        self._env = env

    def fetch_since(self, since: datetime) -> Sequence[Alert]:
        _log.info(
            journal.banner(
                "FETCHING ALERTS",
                owner=self._owner,
                services=", ".join(self._services) or None,
                env=self._env,
                since=since.isoformat(),
            )
        )

        return [
            alert
            for event in self._events_since(since)
            if (alert := self._to_alert(event)) is not None
        ]

    def _events_since(self, since: datetime) -> Iterator[EventResponse]:
        cursor: str | None = None
        while True:
            page = self._search(since, cursor)
            yield from page.data
            cursor = _next_cursor(page)
            if cursor is None:
                return

    def _search(self, since: datetime, cursor: str | None) -> EventsListResponse:
        """Fetch one page, turning any failure of it into the port's own.

        A partial result is indistinguishable from a quiet period, so fail the
        whole fetch. Catch both SDK and transport roots because urllib3 failures
        can escape SDK translation.
        """
        try:
            return self._events.search_events(body=self._request(since, cursor))
        except (OpenApiException, TransportError) as error:
            raise AlertSourceError(
                f"Could not fetch alerts for {self._scope} from Datadog: {error}"
            ) from error

    def _request(self, since: datetime, cursor: str | None) -> EventsListRequest:
        page = EventsRequestPage(limit=PAGE_LIMIT)
        if cursor is not None:
            page.cursor = cursor
        return EventsListRequest(
            filter=EventsQueryFilter(
                query=self._query,
                _from=since.isoformat(),
                to="now",
            ),
            page=page,
        )

    @property
    def _query(self) -> str:
        """Datadog terms are conjunctive, so every resolved scope narrows the fetch."""
        terms = [MONITOR_ALERT_QUERY]
        if self._owner is not None:
            terms.append(f"{OWNER_TAG_PREFIX}{self._owner}")
        if self._services:
            terms.append(f"{SERVICE_TAG_PREFIX}{_any_of(self._services)}")
        terms.append(f"{ENV_TAG_PREFIX}{self._env}")
        return " ".join(terms)

    @property
    def _scope(self) -> str:
        named = [
            f"owner {self._owner!r}" if self._owner is not None else "",
            f"services {', '.join(repr(one) for one in self._services)}"
            if self._services
            else "",
        ]
        return " and ".join(one for one in named if one) + (
            f" in environment {self._env!r}"
        )

    def _to_alert(self, event: EventResponse) -> Alert | None:
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
        )

    def _link_to(self, attributes: object, service: str, fired_at: datetime) -> str:
        """Use monitor pages when available; v2 event ids have no page of their own."""
        window = _window_around(fired_at)
        monitor = getattr(getattr(attributes, "attributes", None), "monitor_id", None)
        if monitor is not None:
            return f"https://{self._web_host}/monitors/{monitor}?{urlencode(window)}"
        if not service:
            return ""
        over_the_service = {
            "query": (
                f"{MONITOR_ALERT_QUERY} {SERVICE_TAG_PREFIX}{service} "
                f"{ENV_TAG_PREFIX}{self._env}"
            ),
            **window,
        }
        return f"https://{self._web_host}/event/explorer?{urlencode(over_the_service)}"


def build_configuration(
    connection: DatadogConnection, ingestion: Ingestion
) -> Configuration:
    """Use the SDK's timeout and retry policy rather than hand-rolling one."""
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
    connection: DatadogConnection,
    ingestion: Ingestion,
    owner: str | None,
    services: Sequence[str] = (),
    *,
    env: str,
) -> DatadogAlertSource:
    client = ApiClient(build_configuration(connection, ingestion))
    return DatadogAlertSource(
        events=EventsApi(client),
        owner=owner,
        web_host=connection.web_host,
        services=services,
        env=env,
    )


def _any_of(names: Sequence[str]) -> str:
    """A single-name group narrows nothing and only adds UI noise."""
    if len(names) == 1:
        return names[0]
    return f"({' OR '.join(names)})"


def _next_cursor(page: EventsListResponse) -> str | None:
    meta = getattr(page, "meta", None)
    return getattr(getattr(meta, "page", None), "after", None)


def _service_of(tags: Sequence[str]) -> str | None:
    for tag in tags:
        if tag.startswith(SERVICE_TAG_PREFIX):
            return tag.removeprefix(SERVICE_TAG_PREFIX)
    return None


def _window_around(fired_at: datetime) -> dict[str, str]:
    return {
        "from_ts": str(int((fired_at - LINK_MARGIN).timestamp() * 1000)),
        "to_ts": str(int((fired_at + LINK_MARGIN).timestamp() * 1000)),
        "live": "false",
    }


def _as_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
