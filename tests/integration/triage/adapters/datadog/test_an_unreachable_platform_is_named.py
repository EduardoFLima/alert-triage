"""Confirms an unreachable platform is named, against the real client stack.

The unit tests raise the transport failure by hand through the injected
endpoint seam, which is what keeps them fast — but it also means they only
prove the adapter catches the exception *they* chose to raise. If the SDK or
urllib3 restructured its exception hierarchy, or began wrapping transport
failures somewhere new, those tests would keep passing while a real run went
back to crashing.

This one drives the real ``ApiClient`` and the real urllib3 at a host that
cannot resolve, so the failure it catches is one the transport genuinely
raised. Unlike the live test beside it, it needs no credential and never
skips: the request fails in transport, long before anything is authenticated,
so dummy keys are enough and CI runs it on every commit.
"""

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
"""A host guaranteed never to resolve.

``.invalid`` is reserved by RFC 2606 for exactly this, so the test cannot be
broken by someone registering the domain, and it fails at name resolution
rather than by reaching a real server.

Applied over the built configuration rather than through ``DatadogConnection``
because the SDK validates ``site`` against its own list of real regions and
refuses an unknown one before any request is made — a good behavior, and the
reason this test reaches past the connection settings to the host itself.
"""

OWNER = "sre"

BOUNDS = Ingestion(request_timeout_seconds=1, max_retries=0)
"""Small enough that failing costs the suite no noticeable time."""

WHEN = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
"""Any instant will do: no server is reached to filter by it."""


def _source_pointed_at_nowhere() -> DatadogAlertSource:
    """The production client and configuration, aimed where nothing answers."""
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
    )


def test_an_unreachable_platform_is_named_rather_than_escaping() -> None:
    with pytest.raises(AlertSourceError) as raised:
        _source_pointed_at_nowhere().fetch_since(WHEN)

    assert OWNER in str(raised.value)


def test_the_transport_failure_is_kept_as_the_cause() -> None:
    """What a developer reads in the log to learn the host never resolved."""
    with pytest.raises(AlertSourceError) as raised:
        _source_pointed_at_nowhere().fetch_since(WHEN)

    assert isinstance(raised.value.__cause__, Exception)
    assert "datadog.invalid" in str(raised.value.__cause__)
