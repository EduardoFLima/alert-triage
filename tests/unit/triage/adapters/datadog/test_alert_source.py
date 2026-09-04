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

from alert_triage.configuration.settings import Ingestion, Scope, ScopedService
from alert_triage.triage.adapters.datadog.alert_source import (
    DatadogAlertSource,
    build_configuration,
)
from alert_triage.triage.adapters.datadog.connection import DatadogConnection
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.ports.alert_source import AlertSourceError

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
    monitor_id: int | None = 12345678,
    message: str | None = None,
) -> EventResponse:
    inner = (
        EventAttributes(title=title)
        if monitor_id is None
        else EventAttributes(title=title, monitor_id=monitor_id)
    )
    said = {} if message is None else {"message": message}
    attributes = EventResponseAttributes(
        timestamp=timestamp,
        tags=["team:sre"] if tags is None else tags,
        attributes=inner,
        **said,
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
        events=FakeEvents(*pages),
        scope=Scope(owner="sre"),
        web_host="app.datadoghq.com",
    )


def _watching(*names: str) -> Scope:
    return Scope(
        owner="sre", services=tuple(ScopedService(name=name) for name in names)
    )


def _transport_failure() -> MaxRetryError:
    """A spent retry bound, shaped exactly as urllib3 raises one.

    The pool is real — constructing one opens no socket — because the error
    carries it and a stand-in would not type-check.
    """
    return MaxRetryError(
        pool=HTTPSConnectionPool(host="api.datadoghq.com", port=443),
        url="/api/v2/events/search",
    )


def test_the_fetch_announces_who_it_is_for_and_how_far_back_it_looks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The first block of a run: without it, nothing below it has a scope."""
    with caplog.at_level(logging.INFO):
        _source(_page()).fetch_since(SINCE)

    written = " ".join(caplog.text.split())
    assert "FETCHING ALERTS" in written
    assert "owner sre" in written
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


def test_the_link_points_at_the_configured_site() -> None:
    source = DatadogAlertSource(
        events=FakeEvents(_page(_event("evt-1", tags=["service:checkout"]))),
        scope=Scope(owner="sre"),
        web_host="app.datadoghq.eu",
    )

    (alert,) = source.fetch_since(SINCE)

    assert urlparse(alert.link).netloc == "app.datadoghq.eu"


def test_an_organisation_on_its_own_subdomain_is_linked_there() -> None:
    """``app`` is where most accounts live, not where every account lives."""
    source = DatadogAlertSource(
        events=FakeEvents(_page(_event("evt-1", tags=["service:checkout"]))),
        scope=Scope(owner="sre"),
        web_host="foobar.datadoghq.eu",
    )

    (alert,) = source.fetch_since(SINCE)

    assert urlparse(alert.link).netloc == "foobar.datadoghq.eu"


def test_an_alert_links_to_the_monitor_that_raised_it() -> None:
    """The event id v2 returns has no page; the monitor that fired has one."""
    source = _source(
        _page(_event("evt-1", tags=["service:checkout"], monitor_id=98765))
    )

    (alert,) = source.fetch_since(SINCE)

    assert urlparse(alert.link).path == "/monitors/98765"
    assert "event/event" not in alert.link


def test_an_alerts_link_is_scoped_to_when_it_fired() -> None:
    """A reader following it days later sees the firing, not the present."""
    source = _source(_page(_event("evt-1", tags=["service:checkout"])))

    (alert,) = source.fetch_since(SINCE)

    parameters = parse_qs(urlparse(alert.link).query)
    fired_at_ms = int(SINCE.timestamp() * 1000)
    assert int(parameters["from_ts"][0]) <= fired_at_ms <= int(parameters["to_ts"][0])
    assert parameters["live"] == ["false"]


def test_an_event_with_no_monitor_falls_back_to_its_services_own_events() -> None:
    """An address over the service beats one known not to open."""
    source = _source(_page(_event("evt-1", tags=["service:checkout"], monitor_id=None)))

    (alert,) = source.fetch_since(SINCE)

    parameters = parse_qs(urlparse(alert.link).query)
    assert urlparse(alert.link).path == "/event/explorer"
    assert "service:checkout" in parameters["query"][0]
    assert int(parameters["from_ts"][0]) <= int(SINCE.timestamp() * 1000)


def test_an_event_nothing_can_be_built_from_keeps_the_empty_default() -> None:
    """A link is a field nobody gave this event, and inventing one is the bug."""
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


def test_the_request_scopes_to_the_owner_in_datadogs_own_terms() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events, scope=Scope(owner="sre"), web_host="app.datadoghq.com"
    )

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert "team:sre" in request.filter.query


def test_the_request_asks_only_for_monitor_alerts() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events, scope=Scope(owner="sre"), web_host="app.datadoghq.com"
    )

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert "source:alert" in request.filter.query


def test_the_request_carries_the_requested_time_bound() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events, scope=Scope(owner="sre"), web_host="app.datadoghq.com"
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
        events=events, scope=Scope(owner="sre"), web_host="app.datadoghq.com"
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


def test_an_unreachable_platform_is_reported_rather_than_escaping() -> None:
    """The failure a run is most likely to meet, and the one it never explained.

    Raised the way the SDK's transport does when the retry bound is spent
    without an answer: past ``ApiException`` entirely, so a catch written for
    the API's own errors never sees it.
    """
    source = _source(_transport_failure())

    with pytest.raises(AlertSourceError, match="sre"):
        source.fetch_since(SINCE)


def test_an_unreachable_platform_part_way_through_pagination_is_reported() -> None:
    source = _source(
        _page(_event("evt-1", tags=["service:checkout"]), after="cursor-1"),
        _transport_failure(),
    )

    with pytest.raises(AlertSourceError):
        source.fetch_since(SINCE)


def test_an_answer_the_client_cannot_interpret_is_reported() -> None:
    """``ApiValueError`` is a sibling of ``ApiException``, not a subclass.

    The SDK's own request path raises it, so catching ``ApiException`` alone
    leaves a second route out of the adapter.
    """
    source = _source(ApiValueError("Invalid value for `data`"))

    with pytest.raises(AlertSourceError, match="sre"):
        source.fetch_since(SINCE)


def test_the_underlying_failure_is_kept_as_the_cause() -> None:
    """A developer reading the log still gets the original, whatever it was."""
    transport = _transport_failure()
    source = _source(transport)

    with pytest.raises(AlertSourceError) as raised:
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


def test_a_scope_naming_services_returns_only_those_services() -> None:
    source = DatadogAlertSource(
        events=FakeEvents(
            _page(
                _event("evt-1", tags=["service:checkout", "team:sre"]),
                _event("evt-2", tags=["service:search", "team:sre"]),
                _event("evt-3", tags=["service:payments", "team:sre"]),
            )
        ),
        scope=_watching("checkout", "payments"),
        web_host="app.datadoghq.com",
    )

    alerts = source.fetch_since(SINCE)

    assert [alert.service for alert in alerts] == ["checkout", "payments"]


def test_a_scope_naming_no_services_keeps_every_one_of_them() -> None:
    source = _source(
        _page(
            _event("evt-1", tags=["service:checkout", "team:sre"]),
            _event("evt-2", tags=["service:search", "team:sre"]),
        )
    )

    alerts = source.fetch_since(SINCE)

    assert [alert.service for alert in alerts] == ["checkout", "search"]


def test_the_request_narrows_to_the_services_the_scope_names() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events,
        scope=_watching("checkout", "payments"),
        web_host="app.datadoghq.com",
    )

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert "service:checkout" in request.filter.query
    assert "service:payments" in request.filter.query
    assert "team:sre" in request.filter.query


def test_a_scope_naming_no_services_leaves_the_query_as_it_was() -> None:
    events = FakeEvents(_page())
    source = DatadogAlertSource(
        events=events, scope=Scope(owner="sre"), web_host="app.datadoghq.com"
    )

    source.fetch_since(SINCE)

    (request,) = events.requests
    assert request.filter.query == "source:alert team:sre"


def _alert_from(message: str | None) -> Alert:
    (alert,) = _source(
        _page(_event("evt-1", tags=["service:checkout"], message=message))
    ).fetch_since(SINCE)
    return alert


def test_the_latency_an_alert_fired_at_is_read_from_its_own_account() -> None:
    alert = _alert_from("Latency is 1400ms")

    assert alert.observed_latency_ms == 1400


def test_a_latency_stated_in_seconds_is_read_as_the_same_duration() -> None:
    """Two alerts stating it differently must compare as the durations they are."""
    assert _alert_from("Latency is 1.4 s").observed_latency_ms == 1400
    assert _alert_from("Latency is 1400 ms").observed_latency_ms == 1400


def test_an_alert_whose_account_states_no_measurement_carries_no_latency() -> None:
    assert _alert_from("The monitor triggered.").observed_latency_ms is None
    assert _alert_from(None).observed_latency_ms is None


def test_a_figure_that_is_not_a_latency_is_not_read_as_one() -> None:
    """An error count or a saturation percentage measures something else."""
    assert _alert_from("Error count is 1400").observed_latency_ms is None
    assert _alert_from("Saturation is 87%").observed_latency_ms is None
    assert _alert_from("Latency SLO burn is 87%").observed_latency_ms is None
    assert _alert_from("Recovered after 30s").observed_latency_ms is None


def test_two_candidate_figures_state_no_single_latency() -> None:
    """A value beside the threshold it crossed: picking one would be a guess."""
    account = "Latency is 1.4s, above the latency threshold of 1s"

    assert _alert_from(account).observed_latency_ms is None


def test_an_unreadable_account_costs_its_sibling_nothing() -> None:
    source = _source(
        _page(
            _event(
                "evt-1",
                tags=["service:checkout"],
                message="Latency is off the charts",
            ),
            _event("evt-2", tags=["service:payments"], message="Latency is 250ms"),
        )
    )

    unreadable, readable = source.fetch_since(SINCE)

    assert unreadable.observed_latency_ms is None
    assert readable.observed_latency_ms == 250
