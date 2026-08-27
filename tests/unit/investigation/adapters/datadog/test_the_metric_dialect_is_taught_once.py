"""The metric grammar every Datadog specialist that queries one is taught.

Each assertion here is a rejection a live account actually returned. The model
writes a metric query the way it writes a log query, and the two grammars look
alike enough that nothing but the instruction stops it.
"""

import pytest

from alert_triage.investigation.adapters.datadog.specialists.apm import (
    APM_INSTRUCTION,
    APM_SPECIALIST,
)
from alert_triage.investigation.adapters.datadog.specialists.dialect import (
    METRIC_CONTEXT_TOOL,
    METRIC_QUERY_DIALECT,
    METRIC_SEARCH_TOOL,
    METRIC_TOOL,
)
from alert_triage.investigation.adapters.datadog.specialists.infrastructure import (
    INFRASTRUCTURE_INSTRUCTION,
    INFRASTRUCTURE_SPECIALIST,
)

QUERYING_METRICS = pytest.mark.parametrize(
    "instruction",
    (APM_INSTRUCTION, INFRASTRUCTURE_INSTRUCTION),
    ids=("apm", "infrastructure"),
)


@QUERYING_METRICS
def test_every_metric_querying_specialist_is_taught_the_same_grammar(
    instruction: str,
) -> None:
    """One account of it, so a correction reaches both."""
    assert METRIC_QUERY_DIALECT in instruction


def test_the_dialect_says_a_comma_separates_tags_and_means_and() -> None:
    assert "{service:checkout,env:prod}" in METRIC_QUERY_DIALECT


def test_the_dialect_forbids_mixing_the_two_filter_grammars() -> None:
    """`'AND' and 'OR' cannot be mixed with ','` — a real 400 from the platform."""
    lowered = METRIC_QUERY_DIALECT.lower()

    assert "mixes them" in lowered or "mixing" in lowered
    assert "{service:checkout,env:prod and !region:eu}" in lowered


def test_the_dialect_warns_that_log_query_syntax_does_not_carry_over() -> None:
    """The specific confusion: the logs specialist is taught AND and OR."""
    assert "log query syntax" in METRIC_QUERY_DIALECT.lower()


def test_the_dialect_explains_a_rejected_aggregation() -> None:
    """`missing_aggregation :: AGG_AVG/AGG_P95` — another real 400."""
    lowered = METRIC_QUERY_DIALECT.lower()

    assert "distribution metric" in lowered
    assert "configuration error" in lowered


def test_a_refused_query_is_never_read_as_a_healthy_service() -> None:
    """The same gate as a failed retrieval, in the one place it is easiest to lose."""
    assert "never report the service as healthy" in METRIC_QUERY_DIALECT.lower()


QUERYING_SPECIALISTS = pytest.mark.parametrize(
    "specialist",
    (APM_SPECIALIST, INFRASTRUCTURE_SPECIALIST),
    ids=("apm", "infrastructure"),
)


@QUERYING_SPECIALISTS
def test_a_specialist_querying_metrics_can_discover_which_ones_exist(
    specialist: object,
) -> None:
    """Guessing a name costs a failed retrieval, which marks the run incomplete."""
    permitted = {
        tool
        for toolset in specialist.toolsets  # type: ignore[attr-defined]
        for tool in toolset.tools
    }

    assert METRIC_SEARCH_TOOL in permitted


def test_the_dialect_sends_a_specialist_to_search_before_it_looks_one_up() -> None:
    """`get_datadog_metric_context` needs a name; only the search finds one."""

    def order(tool: str) -> int:
        """Where the dialect first names this tool, and not a longer one it prefixes."""
        return METRIC_QUERY_DIALECT.index(f"`{tool}`")

    assert order(METRIC_SEARCH_TOOL) < order(METRIC_CONTEXT_TOOL)
    assert order(METRIC_CONTEXT_TOOL) < order(METRIC_TOOL)


def test_the_dialect_forbids_naming_a_metric_no_search_returned() -> None:
    """`metric not found in response: service.latency` — a real failed retrieval."""
    lowered = METRIC_QUERY_DIALECT.lower()

    assert "did not come back from" in lowered or "no search returned" in lowered
    assert "invent" in lowered or "guess" in lowered
