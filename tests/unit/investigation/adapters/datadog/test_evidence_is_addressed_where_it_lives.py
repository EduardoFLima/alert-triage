from datetime import UTC, datetime

import pytest

from alert_triage.investigation.adapters.crew.roster import CREW
from alert_triage.investigation.adapters.crew.specialists.apm import apm_specialist
from alert_triage.investigation.adapters.crew.specialists.trace import (
    trace_specialist,
)
from alert_triage.investigation.adapters.datadog.links import (
    ADDRESSED,
    APM_SERVICE_TOOLS,
    EVENT_TOOLS,
    INFRASTRUCTURE_TOOLS,
    SERVICE_PAGE_ANCHORS,
    TRACE_TOOLS,
    UNADDRESSED,
    DatadogLinks,
)
from alert_triage.investigation.adapters.datadog.mcp import DATADOG
from alert_triage.investigation.contract import Section
from alert_triage.shared.window import Window

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
ONE_PM = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)

FROM_MS = int(NOON.timestamp() * 1000)
TO_MS = int(ONE_PM.timestamp() * 1000)

CHECKOUT = "checkout"

UNPLACED_TOOL = "apm_query_trace"

SEARCH = {
    "query": "service:checkout status:error",
    "from": NOON.isoformat(),
    "to": ONE_PM.isoformat(),
}

METRIC_QUERY = {
    "queries": ["avg:system.cpu.user{service:checkout}"],
    "from": NOON.isoformat(),
    "to": ONE_PM.isoformat(),
}

HALF_A_WINDOW = {"from": NOON.isoformat()}


def _links() -> DatadogLinks:
    return DatadogLinks("app.datadoghq.com")


def test_a_retrieval_from_a_tool_with_no_address_template_has_no_address() -> None:
    assert _links().to_retrieval(UNPLACED_TOOL, METRIC_QUERY, CHECKOUT) is None


def test_a_metric_retrieval_is_addressed_as_the_services_own_apm_page() -> None:
    address = _links().to_retrieval("get_datadog_metric", METRIC_QUERY, CHECKOUT)

    assert address == (
        "https://app.datadoghq.com/apm/entity/service%3Acheckout"
        f"?start={FROM_MS}&end={TO_MS}"
    )


@pytest.mark.parametrize("tool", sorted(APM_SERVICE_TOOLS))
def test_every_apm_tool_opens_the_services_page(tool: str) -> None:
    assert _links().to_retrieval(tool, METRIC_QUERY, CHECKOUT) == _links().to_retrieval(
        "get_datadog_metric", METRIC_QUERY, CHECKOUT
    )


def test_a_span_retrieval_is_addressed_as_the_trace_explorer_over_the_service() -> None:
    address = _links().to_retrieval("search_datadog_spans", SEARCH, CHECKOUT)

    assert address == (
        "https://app.datadoghq.com/apm/traces?query=service%3Acheckout"
        f"&start={FROM_MS}&end={TO_MS}"
    )


@pytest.mark.parametrize("tool", sorted(TRACE_TOOLS))
def test_every_trace_tool_opens_the_service_scoped_trace_explorer(tool: str) -> None:
    assert _links().to_retrieval(tool, SEARCH, CHECKOUT) == _links().to_retrieval(
        "search_datadog_spans", SEARCH, CHECKOUT
    )


def test_a_host_retrieval_is_addressed_as_the_services_infrastructure() -> None:
    address = _links().to_retrieval("search_datadog_hosts", SEARCH, CHECKOUT)

    assert address == (
        "https://app.datadoghq.com/infrastructure?filter=service%3Acheckout"
    )


@pytest.mark.parametrize("tool", sorted(INFRASTRUCTURE_TOOLS))
def test_every_infrastructure_tool_opens_the_services_infrastructure(
    tool: str,
) -> None:
    assert _links().to_retrieval(tool, SEARCH, CHECKOUT) == _links().to_retrieval(
        "search_datadog_hosts", SEARCH, CHECKOUT
    )


def test_an_event_retrieval_is_addressed_as_the_event_explorer_over_the_service() -> (
    None
):
    (event_tool,) = EVENT_TOOLS
    address = _links().to_retrieval(event_tool, SEARCH, CHECKOUT)

    assert address == (
        "https://app.datadoghq.com/event/explorer?query=service%3Acheckout"
        f"&from_ts={FROM_MS}&to_ts={TO_MS}&live=false"
    )


def test_an_apm_address_drops_both_ends_of_an_unreadable_window() -> None:
    address = _links().to_retrieval("get_datadog_metric", HALF_A_WINDOW, CHECKOUT)

    assert address == "https://app.datadoghq.com/apm/entity/service%3Acheckout"


def test_a_trace_address_drops_both_ends_of_an_unreadable_window() -> None:
    address = _links().to_retrieval("search_datadog_spans", HALF_A_WINDOW, CHECKOUT)

    assert address == "https://app.datadoghq.com/apm/traces?query=service%3Acheckout"


def test_an_event_address_drops_both_ends_of_an_unreadable_window() -> None:
    (event_tool,) = EVENT_TOOLS
    address = _links().to_retrieval(event_tool, HALF_A_WINDOW, CHECKOUT)

    assert address == (
        "https://app.datadoghq.com/event/explorer?query=service%3Acheckout&live=false"
    )


def test_a_log_search_is_addressed_exactly_as_it_was_confirmed_live() -> None:
    """The one template already checked against a real account comes out unchanged."""
    address = _links().to_retrieval("search_datadog_logs", SEARCH)

    assert address == (
        "https://app.datadoghq.com/logs?query=service%3Acheckout+status%3Aerror"
        f"&from_ts={int(NOON.timestamp() * 1000)}"
        f"&to_ts={int(ONE_PM.timestamp() * 1000)}&live=false"
    )


def test_a_log_analysis_is_addressed_as_the_search_it_ran_over() -> None:
    assert _links().to_retrieval(
        "analyze_datadog_logs", SEARCH
    ) == _links().to_retrieval("search_datadog_logs", SEARCH)


def test_an_item_from_a_tool_with_no_address_template_inherits_no_log_address() -> None:
    address = _links().to_item(
        UNPLACED_TOOL, {"id": "series-1", "name": "system.cpu.user"}, None
    )

    assert address is None


def test_an_item_from_a_log_tool_is_still_named_on_its_search() -> None:
    retrieval = _links().to_retrieval("search_datadog_logs", SEARCH)

    address = _links().to_item("search_datadog_logs", {"id": "AQAAA-log-1"}, retrieval)

    assert address == f"{retrieval}&event=AQAAA-log-1"


def test_an_item_from_a_log_tool_naming_nothing_falls_back_to_its_search() -> None:
    retrieval = _links().to_retrieval("search_datadog_logs", SEARCH)

    address = _links().to_item("search_datadog_logs", {"message": "OOM"}, retrieval)

    assert address == retrieval


EVERY_DECLARATION = (
    *CREW,
    *(apm_specialist(preview=preview) for preview in (True, False)),
    *(trace_specialist(preview=preview) for preview in (True, False)),
)
"""Includes both Preview branches because deployments may differ."""

DECLARED_TOOLS = sorted(
    {
        tool
        for specialist in EVERY_DECLARATION
        for toolset in specialist.toolsets
        if toolset.provider == DATADOG
        for tool in toolset.tools
    }
)


@pytest.mark.parametrize("tool", DECLARED_TOOLS)
def test_every_tool_the_crew_reaches_is_addressed_or_deliberately_not(
    tool: str,
) -> None:
    assert (tool in ADDRESSED) != (tool in UNADDRESSED)


@pytest.mark.parametrize("tool", sorted(UNADDRESSED))
def test_a_tool_recorded_as_unaddressed_is_given_no_address(tool: str) -> None:
    assert _links().to_retrieval(tool, SEARCH) is None


@pytest.mark.parametrize("tool", sorted(ADDRESSED))
def test_a_tool_recorded_as_addressed_is_given_one(tool: str) -> None:
    assert _links().to_retrieval(tool, SEARCH, CHECKOUT) is not None


@pytest.mark.parametrize("tool", sorted(ADDRESSED | UNADDRESSED))
def test_every_tool_recorded_is_one_the_crew_still_reaches(tool: str) -> None:
    assert tool in DECLARED_TOOLS


SERVICE_SCOPED_TOOLS = sorted(
    APM_SERVICE_TOOLS | TRACE_TOOLS | INFRASTRUCTURE_TOOLS | EVENT_TOOLS
)


@pytest.mark.parametrize("tool", SERVICE_SCOPED_TOOLS)
def test_a_service_scoped_retrieval_with_no_service_has_no_address(tool: str) -> None:
    """``service:`` with nothing after it is a page scoped to nothing."""
    assert _links().to_retrieval(tool, SEARCH, "") is None


def test_a_service_is_encoded_into_the_path_rather_than_pasted() -> None:
    address = _links().to_retrieval("get_datadog_metric", HALF_A_WINDOW, "web/api")

    assert address == "https://app.datadoghq.com/apm/entity/service%3Aweb%2Fapi"


@pytest.mark.parametrize("tool", SERVICE_SCOPED_TOOLS)
def test_an_item_from_a_service_scoped_tool_is_addressed_as_its_retrieval(
    tool: str,
) -> None:
    retrieval = _links().to_retrieval(tool, HALF_A_WINDOW, CHECKOUT)

    address = _links().to_item(tool, {"id": "host-1"}, retrieval, CHECKOUT)

    assert address == retrieval


WINDOW = Window(start=NOON, end=ONE_PM)


def test_a_findings_service_page_opens_on_the_section_it_named() -> None:
    address = _links().to_service(CHECKOUT, WINDOW, Section.INFRASTRUCTURE)

    assert address == (
        "https://app.datadoghq.com/apm/entity/service%3Acheckout"
        f"?start={FROM_MS}&end={TO_MS}#infrastructure"
    )


def test_a_findings_service_page_with_no_section_has_no_anchor() -> None:
    address = _links().to_service(CHECKOUT, WINDOW, None)

    assert address == (
        "https://app.datadoghq.com/apm/entity/service%3Acheckout"
        f"?start={FROM_MS}&end={TO_MS}"
    )


@pytest.mark.parametrize("section", list(Section))
def test_every_section_has_an_anchor_on_the_service_page(section: Section) -> None:
    address = _links().to_service(CHECKOUT, WINDOW, section)

    assert address is not None
    assert address.endswith(f"#{SERVICE_PAGE_ANCHORS[section]}")


def test_a_findings_service_page_needs_a_service() -> None:
    assert _links().to_service("", WINDOW, Section.LOGS) is None


PROD = "prod"


def test_a_log_search_is_not_rewritten_to_the_environment() -> None:
    """It has to open what was retrieved, and that query named no environment."""
    assert _links().to_retrieval(
        "search_datadog_logs", SEARCH, CHECKOUT, PROD
    ) == _links().to_retrieval("search_datadog_logs", SEARCH)


def test_a_composed_apm_page_is_scoped_to_the_environment() -> None:
    address = _links().to_retrieval("get_datadog_metric", METRIC_QUERY, CHECKOUT, PROD)

    assert address == (
        "https://app.datadoghq.com/apm/entity/service%3Acheckout"
        f"?env=prod&start={FROM_MS}&end={TO_MS}"
    )


def test_a_composed_trace_explorer_is_scoped_to_the_environment() -> None:
    address = _links().to_retrieval("search_datadog_spans", SEARCH, CHECKOUT, PROD)

    assert address == (
        "https://app.datadoghq.com/apm/traces?query=service%3Acheckout+env%3Aprod"
        f"&start={FROM_MS}&end={TO_MS}"
    )


def test_a_composed_event_explorer_is_scoped_to_the_environment() -> None:
    address = _links().to_retrieval("search_datadog_events", SEARCH, CHECKOUT, PROD)

    assert address is not None
    assert "query=service%3Acheckout+env%3Aprod" in address


def test_a_findings_service_page_is_scoped_to_the_environment() -> None:
    address = _links().to_service(CHECKOUT, WINDOW, Section.ERRORS, PROD)

    assert address == (
        "https://app.datadoghq.com/apm/entity/service%3Acheckout"
        f"?env=prod&start={FROM_MS}&end={TO_MS}#errors"
    )
