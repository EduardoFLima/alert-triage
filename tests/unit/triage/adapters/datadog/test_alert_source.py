import inspect
import logging
from datetime import UTC, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from datadog_api_client.exceptions import (
    ApiException,
    ApiValueError,
    UnauthorizedException,
)
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
from urllib3 import HTTPSConnectionPool
from urllib3.exceptions import MaxRetryError

from alert_triage.configuration.settings import Ingestion
from alert_triage.triage.adapters.datadog.alert_source import (
    DatadogAlertSource,
    build_configuration,
)
from alert_triage.triage.adapters.datadog.connection import DatadogConnection
from alert_triage.triage.ports.alert_source import AlertSourceError

SINCE = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


class FakeEvents:
    def __init__(self, *pages: EventsListResponse | Exception) -> None:
        self._pages = list(pages)
        self.requests: list[EventsListRequest] = []

    def search_events(self, *, body: EventsListRequest) -> EventsListResponse:
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
    monitor_id: int | None = 12345678,
) -> EventResponse:
    inner = (
        EventAttributes(title=title)
        if monitor_id is None
        else EventAttributes(title=title, monitor_id=monitor_id)
    )
    attributes = EventResponseAttributes(
        timestamp=timestamp,
        tags=["team:sre"] if tags is None else tags,
        attributes=inner,
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
        events=FakeEvents(*pages), owner="sre", web_host="app.datadoghq.com", env="prod"
    )


def _transport_failure() -> MaxRetryError:
    return MaxRetryError(
        pool=HTTPSConnectionPool(host="api.datadoghq.com", port=443),
        url="/api/v2/events/search",
    )


def test_the_fetch_announces_who_it_is_for_and_how_far_back_it_looks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        _source(_page()).fetch_since(SINCE)

    written = " ".join(caplog.text.split())
    assert "FETCHING ALERTS" in written
    assert "owner sre" in written
    assert "env prod" in written
    assert SINCE.isoformat() in written


def test_an_event_is_translated_into_an_alert() -> None:
    source = _source(
        _page(_event("evt-1", tags=["service:checkout", "team:sre"], title="Latency"))
    )

    (alert,) = source.fetch_since(SINCE)

    assert alert.service == "checkout"
    assert alert.fired_at == SINCE
    assert alert.source_id == "evt-1"
    assert alert.title == "Latency"
    assert alert.link.startswith("https://app.datadoghq.com/monitors/12345678")


def test_an_organisation_on_its_own_subdomain_is_linked_there() -> None:
    source = DatadogAlertSource(
        events=FakeEvents(_page(_event("evt-1", tags=["service:checkout"]))),
        owner="sre",
        web_host="foobar.datadoghq.eu",
        env="prod",
    )

    (alert,) = source.fetch_since(SINCE)

    assert urlparse(alert.link).netloc == "foobar.datadoghq.eu"


def test_an_alert_links_to_the_monitor_that_raised_it() -> None:
    source = _source(
        _page(_event("evt-1", tags=["service:checkout"], monitor_id=98765))
    )

    (alert,) = source.fetch_since(SINCE)

    assert urlparse(alert.link).path == "/monitors/98765"
    assert "event/event" not in alert.link


def test_an_alerts_link_is_scoped_to_when_it_fired() -> None:
    source = _source(_page(_event("evt-1", tags=["service:checkout"])))

    (alert,) = source.fetch_since(SINCE)

    parameters = parse_qs(urlparse(alert.link).query)
    fired_at_ms = int(SINCE.timestamp() * 1000)
    assert int(parameters["from_ts"][0]) <= fired_at_ms <= int(parameters["to_ts"][0])
    assert parameters["live"] == ["false"]


def test_an_event_with_no_monitor_falls_back_to_its_services_own_events() -> None:
    source = _source(_page(_event("evt-1", tags=["service:checkout"], monitor_id=None)))

    (alert,) = source.fetch_since(SINCE)

    parameters = parse_qs(urlparse(alert.link).query)
    assert urlparse(alert.link).path == "/event/explorer"
    assert parameters["query"][0].split() == [
        "source:alert",
        "service:checkout",
        "env:prod",
    ]
    assert int(parameters["from_ts"][0]) <= int(SINCE.timestamp() * 1000)


def test_an_event_nothing_can_be_built_from_keeps_the_empty_default() -> None:
    source = _source(
        _page(_event("evt-1", tags=["service:", "team:sre"], monitor_id=None))
    )

    (alert,) = source.fetch_since(SINCE)

    assert alert.link == ""


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


def test_the_request_scopes_to_the_named_services_in_datadogs_own_terms() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events,
        owner=None,
        services=("checkout", "payments"),
        web_host="app.datadoghq.com",
        env="prod",
    )

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert "service:(checkout OR payments)" in request.filter.query
    assert "team:" not in request.filter.query


def test_one_named_service_is_asked_for_by_name() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events,
        owner=None,
        services=("checkout",),
        web_host="app.datadoghq.com",
        env="prod",
    )

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert "service:checkout" in request.filter.query


def test_a_criticality_never_reaches_the_request() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events,
        owner="sre",
        services=("checkout", "payments"),
        web_host="app.datadoghq.com",
        env="prod",
    )

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert "critical" not in request.filter.query


def test_an_owner_alone_asks_for_no_service_at_all() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events,
        owner="sre",
        web_host="app.datadoghq.com",
        env="prod",
    )

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert "service:" not in request.filter.query


def test_a_fetch_bounded_by_services_alone_announces_them(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = DatadogAlertSource(
        events=FakeEvents(_page()),
        owner=None,
        services=("checkout",),
        web_host="app.datadoghq.com",
        env="prod",
    )

    with caplog.at_level(logging.INFO):
        source.fetch_since(SINCE)

    written = " ".join(caplog.text.split())
    assert "checkout" in written
    assert "owner" not in written


def test_a_failure_of_a_service_bounded_fetch_still_says_what_it_was_for() -> None:
    source = DatadogAlertSource(
        events=FakeEvents(ApiException(status=500)),
        owner=None,
        services=("checkout",),
        web_host="app.datadoghq.com",
        env="prod",
    )

    with pytest.raises(AlertSourceError, match="checkout"):
        source.fetch_since(SINCE)


def test_the_request_scopes_to_the_environment_beside_owner_and_services() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events,
        owner="sre",
        services=("checkout",),
        web_host="app.datadoghq.com",
        env="staging",
    )

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert request.filter.query.split() == [
        "source:alert",
        "team:sre",
        "service:checkout",
        "env:staging",
    ]


def test_a_failed_fetch_names_the_environment_it_was_for() -> None:
    with pytest.raises(AlertSourceError, match="environment 'prod'"):
        _source(ApiException(status=500)).fetch_since(SINCE)


def test_a_monitor_link_is_left_as_the_platform_addresses_it() -> None:
    source = _source(_page(_event("evt-1", tags=["service:checkout"])))

    (alert,) = source.fetch_since(SINCE)

    assert "env" not in alert.link


def test_the_request_carries_the_requested_time_bound() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events,
        owner="sre",
        web_host="app.datadoghq.com",
        env="prod",
    )

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
    source = DatadogAlertSource(
        events=events,
        owner="sre",
        web_host="app.datadoghq.com",
        env="prod",
    )

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


def test_an_unreachable_platform_part_way_through_pagination_is_reported() -> None:
    source = _source(
        _page(_event("evt-1", tags=["service:checkout"]), after="cursor-1"),
        _transport_failure(),
    )

    with pytest.raises(AlertSourceError):
        source.fetch_since(SINCE)


def test_an_answer_the_client_cannot_interpret_is_reported() -> None:
    source = _source(ApiValueError("Invalid value for `data`"))

    with pytest.raises(AlertSourceError, match="sre"):
        source.fetch_since(SINCE)


def test_the_underlying_failure_is_kept_as_the_cause() -> None:
    transport = _transport_failure()
    source = _source(transport)

    with pytest.raises(AlertSourceError, match="sre") as raised:
        source.fetch_since(SINCE)

    assert raised.value.__cause__ is transport


def test_the_client_is_bound_by_ingestions_own_timeout_and_retries() -> None:
    configuration = build_configuration(
        DatadogConnection(site="datadoghq.eu", api_key="api", app_key="app"),
        Ingestion(request_timeout_seconds=5, max_retries=2),
    )

    assert configuration.request_timeout == 5
    assert configuration.enable_retry is True
    assert configuration.max_retries == 2


def test_the_investigation_breakers_do_not_reach_the_client() -> None:
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
