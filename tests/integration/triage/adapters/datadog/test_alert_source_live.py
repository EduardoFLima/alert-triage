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
from datadog_api_client import ApiClient
from datadog_api_client.v2.api.events_api import EventsApi
from datadog_api_client.v2.model.events_list_request import EventsListRequest
from datadog_api_client.v2.model.events_query_filter import EventsQueryFilter
from datadog_api_client.v2.model.events_request_page import EventsRequestPage

from alert_triage.configuration.settings import Ingestion, Scope, ScopedService
from alert_triage.triage.adapters.datadog.alert_source import (
    MONITOR_ALERT_QUERY,
    PAGE_LIMIT,
    build_alert_source,
    build_configuration,
)
from alert_triage.triage.adapters.datadog.connection import (
    API_KEY_VARIABLE,
    APP_KEY_VARIABLE,
    resolve_connection,
)
from alert_triage.triage.adapters.datadog.latency import (
    LATENCY_WORDS,
    read_latency_ms,
)
from alert_triage.triage.domain.alert import Alert
from alert_triage.triage.ports.alert_source import AlertSource

pytestmark = pytest.mark.skipif(
    not (os.environ.get(API_KEY_VARIABLE) and os.environ.get(APP_KEY_VARIABLE)),
    reason=f"needs real {API_KEY_VARIABLE} and {APP_KEY_VARIABLE}",
)

OWNER = os.environ.get("SCOPE_OWNER", "sre")

PLAUSIBLE_LATENCY_MS = 10 * 60 * 1000
"""The longest duration a figure read as a latency could plausibly be.

Ten minutes is well past any latency a service reports and well short of the
figures a monitor's prose carries for other reasons — an evaluation window, a
retention period. A reading above it is the reader having taken a number that
was never a latency, which is the failure mode that silences an incident.
"""

LINKS_CHECKED = 3
"""How many of a week's alerts have their address followed.

Every link a run builds takes the same two forms, so following three of them
establishes as much as following three hundred and costs a fraction of a
quiet minute.
"""


def _source() -> AlertSource:
    return build_alert_source(
        resolve_connection(), Ingestion(), scope=Scope(owner=OWNER)
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


def test_the_latency_reader_holds_against_real_monitor_events() -> None:
    """The half a green suite cannot establish: what Datadog's prose says.

    The reader takes a figure out of text a monitor's author wrote, so a fake
    of that text is built from the same assumption the reader is. What this
    asks of a real account is that the reading is *timid*, in the two
    directions it can fail: no account that never mentions a latency yields
    one, and no figure read is outside any duration a service could plausibly
    have taken. A window in which nothing was read at all is a pass — yielding
    nothing costs an investigation nobody needed, which is the failure this
    design chose to have.
    """
    accounts = _recent_accounts()

    if not accounts:
        pytest.skip(f"no monitor events for owner {OWNER!r} in the last week")

    for account in accounts:
        latency = read_latency_ms(account)
        if latency is None:
            continue
        assert _mentions_a_latency(account), (
            f"a latency was read from an account that never mentions one: {account!r}"
        )
        assert 0 <= latency <= PLAUSIBLE_LATENCY_MS, (
            f"{latency}ms was read as a latency out of: {account!r}"
        )


def _mentions_a_latency(account: str) -> bool:
    return any(word in account.lower() for word in LATENCY_WORDS)


def _recent_accounts() -> list[str]:
    """What a week of this owner's monitor events said about why they fired."""
    connection = resolve_connection()
    events = EventsApi(ApiClient(build_configuration(connection, Ingestion())))
    since = datetime.now(UTC) - timedelta(days=7)
    page = events.search_events(
        body=EventsListRequest(
            filter=EventsQueryFilter(
                query=f"{MONITOR_ALERT_QUERY} team:{OWNER}",
                _from=since.isoformat(),
                to="now",
            ),
            page=EventsRequestPage(limit=PAGE_LIMIT),
        )
    )
    return [
        message
        for event in page.data
        if (message := getattr(event.attributes, "message", None))
    ]


def test_a_scope_naming_services_fetches_only_those_services() -> None:
    """Established against the real query grammar, not a canned request body."""
    everything = _source().fetch_since(datetime.now(UTC) - timedelta(days=7))

    if not everything:
        pytest.skip(f"no alerts fired for owner {OWNER!r} in the last week")

    services = sorted({alert.service for alert in everything})
    watched = services[:1]
    narrowed = build_alert_source(
        resolve_connection(),
        Ingestion(),
        scope=Scope(owner=OWNER, services=(ScopedService(name=watched[0]),)),
    ).fetch_since(datetime.now(UTC) - timedelta(days=7))

    assert {alert.service for alert in narrowed} == set(watched)
    if len(services) > 1:
        assert len(narrowed) < len(everything), (
            "narrowing the scope fetched no less than watching every service"
        )
