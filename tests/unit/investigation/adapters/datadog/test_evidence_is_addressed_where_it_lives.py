"""An address opens the kind of thing its retrieval came from, or there is none.

What produced a retrieval depends on which tool was called, so the tool is what
an address is routed on. A tool with no address form known for it answers
``None``: a Log Explorer search built for a metric query looks like an answer
and is an empty page, and a reader cannot tell it from a genuinely empty one.
"""

from datetime import UTC, datetime

import pytest

from alert_triage.investigation.adapters.crew.roster import CREW
from alert_triage.investigation.adapters.crew.specialists.apm import apm_specialist
from alert_triage.investigation.adapters.crew.specialists.trace import (
    trace_specialist,
)
from alert_triage.investigation.adapters.datadog.links import (
    ADDRESSED,
    UNADDRESSED,
    DatadogLinks,
)
from alert_triage.investigation.adapters.datadog.mcp import DATADOG

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
ONE_PM = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)

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


def _links() -> DatadogLinks:
    return DatadogLinks("app.datadoghq.com")


def test_a_retrieval_from_a_tool_with_no_address_form_has_no_address() -> None:
    assert _links().to_retrieval("get_datadog_metric", METRIC_QUERY) is None


def test_a_log_search_is_addressed_exactly_as_it_was_confirmed_live() -> None:
    """The one form already checked against a real account comes out unchanged."""
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


def test_an_item_from_a_tool_with_no_address_form_inherits_no_log_address() -> None:
    """Not even the item-named fallback: there is no search for it to be in."""
    address = _links().to_item(
        "get_datadog_metric", {"id": "series-1", "name": "system.cpu.user"}, None
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
"""The crew as declared for an account with Preview access and one without.

``CREW`` is built for one of the two, and a tool reached only by the other is
still a tool a deployment's evidence comes from.
"""

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
    """A specialist widened later must not lose its addresses unnoticed."""
    assert (tool in ADDRESSED) != (tool in UNADDRESSED)


@pytest.mark.parametrize("tool", sorted(UNADDRESSED))
def test_a_tool_recorded_as_unaddressed_is_given_no_address(tool: str) -> None:
    assert _links().to_retrieval(tool, SEARCH) is None


@pytest.mark.parametrize("tool", sorted(ADDRESSED))
def test_a_tool_recorded_as_addressed_is_given_one(tool: str) -> None:
    assert _links().to_retrieval(tool, SEARCH) is not None


@pytest.mark.parametrize("tool", sorted(ADDRESSED | UNADDRESSED))
def test_every_tool_recorded_is_one_the_crew_still_reaches(tool: str) -> None:
    """A record for a tool nobody declares is a decision about nothing."""
    assert tool in DECLARED_TOOLS
