"""Confirms the payload shape the unit tests assume, against a real account.

The unit tests are written against canned event payloads, which is what makes
them fast and offline — but it also means a wrong assumption about Datadog's
schema would pass them. This test is the one that would catch it. It needs a
real credential and is skipped without one, so CI and a fresh clone stay green.
"""

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from alert_triage.configuration.settings import Ingestion
from alert_triage.triage.adapters.datadog.alert_source import build_alert_source
from alert_triage.triage.adapters.datadog.connection import (
    API_KEY_VARIABLE,
    APP_KEY_VARIABLE,
    resolve_connection,
)
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.ports.alert_source import AlertSource

pytestmark = pytest.mark.skipif(
    not (os.environ.get(API_KEY_VARIABLE) and os.environ.get(APP_KEY_VARIABLE)),
    reason=f"needs real {API_KEY_VARIABLE} and {APP_KEY_VARIABLE}",
)

OWNER = os.environ.get("SCOPE_OWNER", "sre")

LINKS_CHECKED = 3
"""How many of a week's alerts have their address followed.

Every link a run builds takes the same two forms, so following three of them
establishes as much as following three hundred and costs a fraction of a
quiet minute.
"""


def _source(owner: str | None = OWNER, services: tuple[str, ...] = ()) -> AlertSource:
    return build_alert_source(
        resolve_connection(), Ingestion(), owner=owner, services=services
    )


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
        assert alert.link
        assert alert.fired_at.tzinfo is UTC


def test_a_translated_alerts_link_opens_rather_than_404s(
    answers: Callable[[str], bool],
) -> None:
    """The check the link this replaced would have failed, and nothing else could.

    A unit test can only assert the string it composed. Whether Datadog serves
    a page at that address is a question only Datadog answers, and the previous
    link — the v2 event id in the v1 event route — passed every unit test while
    answering nobody.
    """
    alerts = _source().fetch_since(datetime.now(UTC) - timedelta(days=7))

    if not alerts:
        pytest.skip(f"no alerts fired for owner {OWNER!r} in the last week")

    for alert in alerts[:LINKS_CHECKED]:
        assert answers(alert.link), f"the platform serves nothing at {alert.link}"


def test_a_service_scoped_fetch_is_a_query_the_platform_answers() -> None:
    """The composed `service:` term, which no fake can accept or reject for us.

    The names are taken from what actually fired rather than written down here,
    so this asks the account about services it really carries. Two of them when
    the week offered two, which is what puts the grouped form of the term in
    front of the platform.
    """
    week = datetime.now(UTC) - timedelta(days=7)
    alerts = _source().fetch_since(week)

    if not alerts:
        pytest.skip(f"no alerts fired for owner {OWNER!r} in the last week")
    named = tuple(sorted({alert.service for alert in alerts})[:2])

    scoped = _source(owner=None, services=named).fetch_since(week)

    assert scoped, f"the platform answered nothing for services {named}"
    assert {alert.service for alert in scoped} <= set(named)


def test_both_filters_narrow_a_real_fetch_together() -> None:
    """Naming services within an owner asks for those services *of* that owner."""
    week = datetime.now(UTC) - timedelta(days=7)
    alerts = _source().fetch_since(week)

    if not alerts:
        pytest.skip(f"no alerts fired for owner {OWNER!r} in the last week")
    named = tuple(sorted({alert.service for alert in alerts})[:1])

    both = _source(services=named).fetch_since(week)

    assert {alert.service for alert in both} == set(named)
