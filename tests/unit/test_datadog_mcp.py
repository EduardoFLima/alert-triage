from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from alert_triage.adapters.datadog.connection import DatadogConnection
from alert_triage.adapters.datadog.datadog_mcp import (
    API_KEY_HEADER,
    APP_KEY_HEADER,
    LOGS_TOOLSET,
    mcp_endpoint,
    mcp_headers,
    records_from,
)
from alert_triage.domain.findings import LogRecord
from alert_triage.domain.window import Window
from alert_triage.ports.observability_platform import ObservabilityPlatformError

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
WINDOW = Window(start=NOON, end=NOON + timedelta(minutes=7))


def _connection(site: str = "datadoghq.com") -> DatadogConnection:
    return DatadogConnection(site=site, api_key="api", app_key="app")


def test_the_endpoint_is_derived_from_the_default_site() -> None:
    assert mcp_endpoint(_connection()).startswith("https://mcp.datadoghq.com/")


def test_the_endpoint_follows_a_non_default_site() -> None:
    """A region is a deployment fact; pointing at another one changes no code."""
    assert mcp_endpoint(_connection("datadoghq.eu")).startswith(
        "https://mcp.datadoghq.eu/"
    )


def test_the_endpoint_asks_only_for_the_toolset_the_port_needs() -> None:
    assert f"toolsets={LOGS_TOOLSET}" in mcp_endpoint(_connection())


def test_the_headers_are_the_ones_the_server_expects() -> None:
    """The server's header is DD_APPLICATION_KEY; our variable is DD_APP_KEY."""
    headers = mcp_headers(_connection())

    assert headers[API_KEY_HEADER] == "api"
    assert headers[APP_KEY_HEADER] == "app"
    assert APP_KEY_HEADER == "DD_APPLICATION_KEY"


def _payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "timestamp": "2026-08-15T12:00:00+00:00",
        "status": "error",
        "message": "container OOMKilled",
        "service": "checkout",
    }
    payload.update(overrides)
    return payload


def test_a_returned_log_becomes_a_domain_record() -> None:
    (record,) = records_from([_payload()])

    assert record == LogRecord(
        timestamp=NOON, level="error", message="container OOMKilled", service="checkout"
    )


def test_several_returned_logs_keep_their_order() -> None:
    records = records_from(
        [_payload(message="first"), _payload(message="second", status="warn")]
    )

    assert [record.message for record in records] == ["first", "second"]
    assert records[1].level == "warn"


def test_nothing_returned_is_an_empty_result_rather_than_a_failure() -> None:
    """A quiet service is a finding; it is not an error."""
    assert records_from([]) == ()


def test_a_payload_missing_what_identifies_a_line_is_refused() -> None:
    with pytest.raises(ObservabilityPlatformError):
        records_from([{"status": "error"}])


def test_a_payload_whose_timestamp_cannot_be_read_is_refused() -> None:
    with pytest.raises(ObservabilityPlatformError):
        records_from([_payload(timestamp="the day before yesterday")])


def test_a_payload_that_is_not_a_record_at_all_is_refused() -> None:
    with pytest.raises(ObservabilityPlatformError):
        records_from(["container OOMKilled"])
