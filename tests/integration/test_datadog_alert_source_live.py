"""Confirms the payload shape the unit tests assume, against a real account.

The unit tests are written against canned event payloads, which is what makes
them fast and offline — but it also means a wrong assumption about Datadog's
schema would pass them. This test is the one that would catch it. It needs a
real credential and is skipped without one, so CI and a fresh clone stay green.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.adapters.datadog.alert_source import build_alert_source
from alert_triage.adapters.datadog.connection import (
    API_KEY_VARIABLE,
    APP_KEY_VARIABLE,
    resolve_connection,
)
from alert_triage.configuration.settings import Ingestion
from alert_triage.domain.alert import Alert
from alert_triage.ports.alert_source import AlertSource

pytestmark = pytest.mark.skipif(
    not (os.environ.get(API_KEY_VARIABLE) and os.environ.get(APP_KEY_VARIABLE)),
    reason=f"needs real {API_KEY_VARIABLE} and {APP_KEY_VARIABLE}",
)

OWNER = os.environ.get("SCOPE_OWNER", "sre")


def _source() -> AlertSource:
    return build_alert_source(resolve_connection(), Ingestion(), owner=OWNER)


def test_a_real_fetch_succeeds_and_yields_alerts() -> None:
    """A quiet window is a valid answer; what must not happen is an exception."""
    source = _source()

    alerts = source.fetch_since(datetime.now(UTC) - Ingestion().lookback)

    assert all(isinstance(alert, Alert) for alert in alerts)


def test_every_translated_alert_carries_the_fields_the_unit_tests_assume() -> None:
    source = _source()

    alerts = source.fetch_since(datetime.now(UTC) - timedelta(days=7))

    if not alerts:
        pytest.skip(f"no alerts fired for owner {OWNER!r} in the last week")

    for alert in alerts:
        assert alert.service
        assert alert.source_id
        assert alert.link.endswith(alert.source_id)
        assert alert.fired_at.tzinfo is UTC
