"""A Datadog tool's facts, stated once for every specialist that reaches it.

What a tool is called, which toolset serves it, and what it does are facts
about the platform, not choices a specialist makes. Two specialists that share a
tool used to state them twice, so one could drift without the other noticing.
"""

import pytest

from alert_triage.investigation.adapters.datadog.mcp import DATADOG
from alert_triage.investigation.adapters.datadog.tools import (
    DatadogTool,
    described,
    toolsets,
)
from alert_triage.investigation.domain.specialist import Toolset

METRIC = DatadogTool("get_datadog_metric", "core", "returns a metric's values.")
HOSTS = DatadogTool("search_datadog_hosts", "core", "finds the hosts.")
WORKLOADS = DatadogTool("search_datadog_k8s_resources", "kubernetes", "finds them.")


def test_a_tool_holds_its_name_its_toolset_and_what_it_does() -> None:
    tool = DatadogTool(
        name="get_datadog_metric",
        toolset="core",
        description="returns a metric's values over a time range.",
    )

    assert tool.name == "get_datadog_metric"
    assert tool.toolset == "core"
    assert tool.description == "returns a metric's values over a time range."


@pytest.mark.parametrize(
    "blank",
    ("name", "toolset", "description"),
)
def test_a_tool_missing_any_of_them_is_rejected(blank: str) -> None:
    """A nameless tool cannot be permitted, and an undescribed one cannot be told."""
    fields = {
        "name": "get_datadog_metric",
        "toolset": "core",
        "description": "returns a metric's values over a time range.",
    }
    fields[blank] = "  "

    with pytest.raises(ValueError, match=blank):
        DatadogTool(**fields)


def test_tools_are_asked_for_by_the_toolset_serving_them() -> None:
    """A declaration picks tools; which group each is in is not its to say."""
    assert toolsets(METRIC, WORKLOADS, HOSTS) == (
        Toolset(
            provider=DATADOG,
            name="core",
            tools=("get_datadog_metric", "search_datadog_hosts"),
        ),
        Toolset(
            provider=DATADOG,
            name="kubernetes",
            tools=("search_datadog_k8s_resources",),
        ),
    )


def test_toolsets_keep_the_order_their_tools_were_picked_in() -> None:
    assert [toolset.name for toolset in toolsets(WORKLOADS, METRIC)] == [
        "kubernetes",
        "core",
    ]


def test_tools_are_described_as_a_list_in_the_order_given() -> None:
    assert described(HOSTS, METRIC) == (
        "- `search_datadog_hosts` finds the hosts.\n"
        "- `get_datadog_metric` returns a metric's values."
    )


def test_a_long_description_wraps_under_its_bullet() -> None:
    long = DatadogTool(
        "search_datadog_metrics",
        "core",
        "lists the metrics that exist, filtered by name or by tag — "
        "`service:the-service` is how you narrow it to one service's.",
    )

    first, *rest = described(long).splitlines()

    assert first.startswith("- `search_datadog_metrics` lists")
    assert rest
    assert all(line.startswith("  ") and len(line) <= 79 for line in rest)


def test_a_quoted_span_is_never_split_across_lines() -> None:
    """A tool or a query split mid-quote is one the model reads as two."""
    long = DatadogTool(
        "search_datadog_metrics",
        "core",
        "narrows to one service's metrics by the tag that service is reported "
        "under, which is written as `service:a-rather-long-service-name` and "
        "nothing else.",
    )

    assert "`service:a-rather-long-service-name`" in described(long)
