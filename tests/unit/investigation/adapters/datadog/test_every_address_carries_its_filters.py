"""An address that filters nothing is a page, and a page is not evidence.

Every address carries the service the incident is about and the window its
alerts span, and each carries whatever else identifies the thing retrieved — the
log item, the metric. The service and the window come from the investigation
rather than from the tool's arguments: a tool called without them still produced
evidence about one service over one window, and a reader following the link
wants both.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from alert_triage.investigation.adapters.datadog.links import DatadogLinks
from alert_triage.investigation.contract import InvestigationTarget
from alert_triage.shared.window import Window

HOST = "app.datadoghq.eu"
NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
LATER = NOON + timedelta(minutes=30)

FROM_MS = str(int(NOON.timestamp() * 1000))
TO_MS = str(int(LATER.timestamp() * 1000))

ABOUT = InvestigationTarget(
    service="checkout", window=Window(start=NOON, end=LATER), alert_count=3
)

SERVICE_SCOPED = (
    "search_datadog_logs",
    "search_datadog_spans",
    "get_datadog_trace",
    "search_datadog_service_dependencies",
    "search_datadog_k8s_resources",
    "describe_datadog_k8s_resource",
    "search_datadog_hosts",
)
"""Products whose evidence is about a service, and which are narrowed to it."""

METRIC_TOOLS = (
    "search_datadog_metrics",
    "get_datadog_metric_context",
    "get_datadog_metric",
)
"""Metrics are not necessarily a service's. A host or pod metric carries no
``service`` tag at all, so scoping one to the service that alerted graphs
nothing — see the scope tests below."""

FILTERED = SERVICE_SCOPED + METRIC_TOOLS


def _address(tool: str, args: dict[str, object] | None = None) -> str:
    built = DatadogLinks(HOST).to_retrieval(args or {}, tool=tool, about=ABOUT)
    assert built is not None, f"{tool} built no address"
    return built


def _parameters(address: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(address).query)


@pytest.mark.parametrize("tool", FILTERED)
def test_every_address_is_pinned_to_the_incidents_window(tool: str) -> None:
    """A page showing the last fifteen minutes is not showing the incident."""
    assert {FROM_MS, TO_MS} <= {
        value for values in _parameters(_address(tool)).values() for value in values
    }


@pytest.mark.parametrize("tool", SERVICE_SCOPED)
def test_a_services_evidence_names_the_service_the_incident_is_about(
    tool: str,
) -> None:
    assert "checkout" in unquote(_address(tool))


@pytest.mark.parametrize("tool", FILTERED)
def test_no_address_is_ever_built_without_a_period(tool: str) -> None:
    """Whatever else a link carries or does not, it opens on the right period."""
    values = {
        value for values in _parameters(_address(tool, {})).values() for value in values
    }

    assert {FROM_MS, TO_MS} <= values


def test_a_log_address_carries_the_query_the_model_actually_searched() -> None:
    address = _address(
        "search_datadog_logs", {"query": "service:checkout @http.status_code:503"}
    )

    assert _parameters(address)["query"] == ["service:checkout @http.status_code:503"]


def test_a_log_address_falls_back_to_the_service_when_no_query_was_given() -> None:
    assert _parameters(_address("search_datadog_logs"))["query"] == ["service:checkout"]


def test_a_metric_address_names_the_metric_that_was_queried() -> None:
    """`kubernetes.memory.usage` beside an empty explorer told a reader nothing."""
    address = _address(
        "get_datadog_metric",
        {"query": "avg:kubernetes.memory.usage{service:checkout}"},
    )
    parameters = _parameters(address)

    assert parameters["exp_metric"] == ["kubernetes.memory.usage"]
    assert parameters["exp_scope"] == ["service:checkout"]
    assert parameters["exp_agg"] == ["avg"]


def test_a_metric_keeps_the_scope_it_was_gathered_under() -> None:
    """A pod metric carries no service tag; scoping it to one graphs nothing."""
    address = _address(
        "get_datadog_metric",
        {"query": "avg:kubernetes.memory.usage{pod_name:checkout-7f4b}"},
    )

    assert _parameters(address)["exp_scope"] == ["pod_name:checkout-7f4b"]
    assert "service:checkout" not in unquote(address)


def test_a_metric_gathered_across_everything_stays_across_everything() -> None:
    """`*` is a scope the model chose, not an absence to fill in."""
    address = _address("get_datadog_metric", {"query": "avg:system.cpu.user{*}"})

    assert _parameters(address)["exp_metric"] == ["system.cpu.user"]
    assert _parameters(address)["exp_scope"] == ["*"]


def test_a_metric_address_still_opens_when_the_query_cannot_be_read() -> None:
    """A query in a shape nobody anticipated costs the metric, not the period."""
    address = _address("get_datadog_metric", {"query": "!!!"})
    parameters = _parameters(address)

    assert address.startswith(f"https://{HOST}/metric/explorer")
    assert "exp_scope" not in parameters
    assert parameters["start"] == [FROM_MS]
