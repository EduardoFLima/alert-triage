from datetime import UTC, datetime

import pytest
from datadog_api_client import ApiClient
from datadog_api_client.v2.api.events_api import EventsApi

from alert_triage.configuration.settings import Ingestion
from alert_triage.triage.adapters.datadog.alert_source import (
    DatadogAlertSource,
    build_configuration,
)
from alert_triage.triage.adapters.datadog.connection import DatadogConnection
from alert_triage.triage.ports.alert_source import AlertSourceError

UNREACHABLE_HOST = "https://api.datadog.invalid"

OWNER = "sre"

BOUNDS = Ingestion(request_timeout_seconds=1, max_retries=0)

WHEN = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def _source_pointed_at_nowhere() -> DatadogAlertSource:
    configuration = build_configuration(
        DatadogConnection(
            site="datadoghq.com", api_key="not-a-real-key", app_key="not-a-real-key"
        ),
        BOUNDS,
    )
    configuration.host = UNREACHABLE_HOST
    return DatadogAlertSource(
        events=EventsApi(ApiClient(configuration)),
        owner=OWNER,
        web_host="app.datadoghq.com",
        env="prod",
    )


def test_an_unreachable_platform_is_named_and_kept_as_the_cause() -> None:
    with pytest.raises(AlertSourceError) as raised:
        _source_pointed_at_nowhere().fetch_since(WHEN)

    assert OWNER in str(raised.value)
    assert isinstance(raised.value.__cause__, Exception)
    assert "datadog.invalid" in str(raised.value.__cause__)
