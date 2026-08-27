"""An address opens the product the evidence came from, not always the logs.

Every retrieval used to be addressed as a Log Explorer search, which was right
while logs were all a specialist could ask for. A metric retrieval addressed
that way sends a reader to the wrong product with a metric query pasted into a
log search — a link that opens, and opens on nothing.

What decides is the tool, not the specialist. Two specialists reaching the same
tool want the same page, and one specialist reaching four tools wants four
different ones.
"""

import pytest

from alert_triage.investigation.adapters.adk.crew import CREW
from alert_triage.investigation.adapters.datadog.links import (
    DATADOG_DESTINATIONS,
    UNADDRESSED_TOOLS,
    DatadogLinks,
)

HOST = "app.datadoghq.com"
SEARCH = {
    "query": "service:checkout",
    "service": "checkout",
    "from": 1_755_000_000,
    "to": 1_755_003_600,
}
"""What a tool was called with. Carries a service, since some pages are one."""


def _address(tool: str) -> str | None:
    return DatadogLinks(HOST).to_retrieval(SEARCH, tool=tool)


@pytest.mark.parametrize(
    ("tool", "path"),
    (
        ("search_datadog_logs", "/logs"),
        ("analyze_datadog_logs", "/logs"),
        ("search_datadog_spans", "/apm/traces"),
        ("get_datadog_trace", "/apm/traces"),
        ("get_datadog_metric", "/metric/explorer"),
        ("get_datadog_metric_context", "/metric/explorer"),
        ("search_datadog_hosts", "/infrastructure"),
        ("search_datadog_k8s_resources", "/orchestration/overview"),
        ("describe_datadog_k8s_resource", "/orchestration/overview"),
        ("search_datadog_service_dependencies", "/apm/entity/"),
    ),
)
def test_a_retrieval_opens_the_product_it_came_from(tool: str, path: str) -> None:
    address = _address(tool)

    assert address is not None
    assert address.startswith(f"https://{HOST}{path}")


def test_a_metric_retrieval_is_not_addressed_as_a_log_search() -> None:
    """The bug this fixes: the wrong product, with a metric query in it."""
    address = _address("get_datadog_metric")

    assert address is not None
    assert "/logs" not in address


def test_a_tool_with_no_documented_page_is_left_unaddressed() -> None:
    """A link to the wrong page is worse than no link, which is why none is built."""
    assert _address("search_datadog_events") is None


def test_an_unknown_tool_is_left_unaddressed() -> None:
    assert _address("some_tool_nobody_declared") is None


def test_an_item_is_named_only_where_its_page_can_open_one() -> None:
    """Anchoring an item onto a page that cannot show one is a broken address."""
    logs = _address("search_datadog_logs")
    metrics = _address("get_datadog_metric")
    item = {"id": "AQAAA-log-1"}

    addressed = DatadogLinks(HOST).to_item(item, logs, tool="search_datadog_logs")
    plain = DatadogLinks(HOST).to_item(item, metrics, tool="get_datadog_metric")

    assert addressed is not None and "AQAAA-log-1" in addressed
    assert plain == metrics


@pytest.mark.parametrize(
    "tool",
    sorted(
        {tool for one in CREW for toolset in one.toolsets for tool in toolset.tools}
    ),
)
def test_every_tool_the_crew_declares_is_addressed_or_deliberately_not(
    tool: str,
) -> None:
    """A specialist added later cannot quietly inherit somebody else's page."""
    assert tool in DATADOG_DESTINATIONS or tool in UNADDRESSED_TOOLS


def test_a_services_evidence_opens_that_services_own_apm_page() -> None:
    """The service page, not the catalogue list: `/apm/entity/service%3A<name>`."""
    address = DatadogLinks(HOST).to_retrieval(
        {"service": "checkout"}, tool="search_datadog_service_dependencies"
    )

    assert address == f"https://{HOST}/apm/entity/service%3Acheckout"


def test_a_service_name_is_encoded_rather_than_pasted_into_the_path() -> None:
    address = DatadogLinks(HOST).to_retrieval(
        {"service": "shop/ist cart"}, tool="search_datadog_service_dependencies"
    )

    assert address is not None
    assert " " not in address
    assert "/apm/entity/service%3A" in address


def test_a_service_page_falls_back_to_the_catalogue_when_no_service_was_named() -> None:
    """A page for no service is a 404; the catalogue is the honest degradation."""
    address = DatadogLinks(HOST).to_retrieval(
        {}, tool="search_datadog_service_dependencies"
    )

    assert address == f"https://{HOST}/services"
