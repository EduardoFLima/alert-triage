import inspect
from datetime import UTC, datetime, timedelta, timezone

import pytest
from datadog_api_client.exceptions import ApiException, UnauthorizedException
from datadog_api_client.v2.model.event_attributes import EventAttributes
from datadog_api_client.v2.model.event_response import EventResponse
from datadog_api_client.v2.model.event_response_attributes import (
    EventResponseAttributes,
)
from datadog_api_client.v2.model.events_list_request import EventsListRequest
from datadog_api_client.v2.model.events_list_response import EventsListResponse
from datadog_api_client.v2.model.events_response_metadata import EventsResponseMetadata
from datadog_api_client.v2.model.events_response_metadata_page import (
    EventsResponseMetadataPage,
)

from alert_triage.adapters.datadog.alert_source import (
    DatadogAlertSource,
    build_configuration,
)
from alert_triage.adapters.datadog.connection import DatadogConnection
from alert_triage.ports.alert_source import AlertSourceError
from alert_triage.ports.config import Ingestion

SINCE = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


class FakeEvents:
    """Stands in for the SDK's events endpoint, returning canned pages."""

    def __init__(self, *pages: EventsListResponse | Exception) -> None:
        """Hold the pages to hand back, one per call, in order."""
        self._pages = list(pages)
        self.requests: list[EventsListRequest] = []

    def search_events(self, *, body: EventsListRequest) -> EventsListResponse:
        """Record the request and reply with the next canned page."""
        self.requests.append(body)
        page = self._pages[len(self.requests) - 1]
        if isinstance(page, Exception):
            raise page
        return page


def _event(
    identifier: str,
    *,
    tags: list[str] | None = None,
    title: str = "Latency above threshold",
    timestamp: datetime = SINCE,
) -> EventResponse:
    attributes = EventResponseAttributes(
        timestamp=timestamp,
        tags=["team:sre"] if tags is None else tags,
        attributes=EventAttributes(title=title),
    )
    return EventResponse(id=identifier, attributes=attributes)


def _page(*events: EventResponse, after: str | None = None) -> EventsListResponse:
    if after is None:
        return EventsListResponse(data=list(events))
    return EventsListResponse(
        data=list(events),
        meta=EventsResponseMetadata(page=EventsResponseMetadataPage(after=after)),
    )


def _source(*pages: EventsListResponse | Exception) -> DatadogAlertSource:
    return DatadogAlertSource(
        events=FakeEvents(*pages), owner="sre", site="datadoghq.com"
    )


def test_an_event_is_translated_into_an_alert() -> None:
    source = _source(
        _page(_event("evt-1", tags=["service:checkout", "team:sre"], title="Latency"))
    )

    (alert,) = source.fetch_since(SINCE)

    assert alert.service == "checkout"
    assert alert.fired_at == SINCE
    assert alert.source_id == "evt-1"
    assert alert.title == "Latency"
    assert alert.link == "https://app.datadoghq.com/event/event?id=evt-1"


def test_the_link_points_at_the_configured_site() -> None:
    source = DatadogAlertSource(
        events=FakeEvents(_page(_event("evt-1", tags=["service:checkout"]))),
        owner="sre",
        site="datadoghq.eu",
    )

    (alert,) = source.fetch_since(SINCE)

    assert alert.link == "https://app.datadoghq.eu/event/event?id=evt-1"


def test_a_fire_time_in_another_zone_is_expressed_in_utc() -> None:
    tokyo = timezone(timedelta(hours=9))
    fired = datetime(2026, 8, 7, 21, 0, tzinfo=tokyo)
    source = _source(_page(_event("evt-1", tags=["service:checkout"], timestamp=fired)))

    (alert,) = source.fetch_since(SINCE)

    assert alert.fired_at.tzinfo is UTC
    assert alert.fired_at == datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def test_a_naive_fire_time_is_read_as_utc() -> None:
    source = _source(
        _page(
            _event(
                "evt-1",
                tags=["service:checkout"],
                timestamp=datetime(2026, 8, 7, 12, 0),
            )
        )
    )

    (alert,) = source.fetch_since(SINCE)

    assert alert.fired_at == SINCE


def test_the_request_scopes_to_the_owner_in_datadogs_own_terms() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(events=events, owner="sre", site="datadoghq.com")

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert "team:sre" in request.filter.query


def test_the_request_asks_only_for_monitor_alerts() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(events=events, owner="sre", site="datadoghq.com")

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert "source:alert" in request.filter.query


def test_the_request_carries_the_requested_time_bound() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(events=events, owner="sre", site="datadoghq.com")

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert request.filter._from == SINCE.isoformat()
    assert request.filter.to == "now"


def test_alerts_from_every_cursor_page_are_returned() -> None:
    events = FakeEvents(
        _page(_event("evt-1", tags=["service:checkout"]), after="cursor-1"),
        _page(_event("evt-2", tags=["service:checkout"]), after="cursor-2"),
        _page(_event("evt-3", tags=["service:payments"])),
    )
    source = DatadogAlertSource(events=events, owner="sre", site="datadoghq.com")

    alerts = source.fetch_since(SINCE)

    assert [alert.source_id for alert in alerts] == ["evt-1", "evt-2", "evt-3"]
    assert [getattr(request.page, "cursor", None) for request in events.requests] == [
        None,
        "cursor-1",
        "cursor-2",
    ]


def test_a_run_matching_nothing_succeeds_with_no_alerts() -> None:
    source = _source(_page())

    assert source.fetch_since(SINCE) == []


def test_an_event_without_a_service_tag_is_excluded_from_its_siblings() -> None:
    source = _source(
        _page(
            _event("evt-1", tags=["service:checkout", "team:sre"]),
            _event("evt-2", tags=["team:sre"]),
            _event("evt-3", tags=["service:payments"]),
        )
    )

    alerts = source.fetch_since(SINCE)

    assert [alert.source_id for alert in alerts] == ["evt-1", "evt-3"]
    assert {alert.service for alert in alerts} == {"checkout", "payments"}


def test_rejected_credentials_are_reported_rather_than_read_as_a_quiet_period() -> None:
    source = _source(UnauthorizedException(status=403, reason="Forbidden"))

    with pytest.raises(AlertSourceError, match="Forbidden"):
        source.fetch_since(SINCE)


def test_a_failure_part_way_through_pagination_discards_the_pages_retrieved() -> None:
    source = _source(
        _page(_event("evt-1", tags=["service:checkout"]), after="cursor-1"),
        ApiException(status=500, reason="Internal Server Error"),
    )

    with pytest.raises(AlertSourceError):
        source.fetch_since(SINCE)


def test_the_client_is_bound_by_ingestions_own_timeout_and_retries() -> None:
    configuration = build_configuration(
        DatadogConnection(site="datadoghq.eu", api_key="api", app_key="app"),
        Ingestion(request_timeout_seconds=5, max_retries=2),
    )

    assert configuration.request_timeout == 5
    assert configuration.enable_retry is True
    assert configuration.max_retries == 2


def test_the_investigation_breakers_do_not_reach_the_client() -> None:
    """The breakers bound investigation; they are not an input to this client."""
    parameters = inspect.signature(build_configuration).parameters
    assert [parameter.annotation for parameter in parameters.values()] == [
        DatadogConnection,
        Ingestion,
    ]

    configuration = build_configuration(
        DatadogConnection(site="datadoghq.com", api_key="api", app_key="app"),
        Ingestion(),
    )

    assert configuration.request_timeout == Ingestion().request_timeout_seconds
    assert configuration.max_retries == Ingestion().max_retries


def test_the_client_is_pointed_at_the_configured_site_and_credentials() -> None:
    configuration = build_configuration(
        DatadogConnection(site="datadoghq.eu", api_key="api", app_key="app"),
        Ingestion(),
    )

    assert configuration.server_variables["site"] == "datadoghq.eu"
    assert configuration.api_key["apiKeyAuth"] == "api"
    assert configuration.api_key["appKeyAuth"] == "app"
