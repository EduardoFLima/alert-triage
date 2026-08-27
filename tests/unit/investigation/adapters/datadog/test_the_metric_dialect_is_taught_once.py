"""The metric grammar every Datadog specialist that queries one is taught.

Each assertion here is a rejection a live account actually returned. The model
writes a metric query the way it writes a log query, and the two grammars look
alike enough that nothing but the instruction stops it.
"""

import pytest

from alert_triage.investigation.adapters.datadog.specialists.apm import APM_INSTRUCTION
from alert_triage.investigation.adapters.datadog.specialists.dialect import (
    METRIC_QUERY_DIALECT,
)
from alert_triage.investigation.adapters.datadog.specialists.infrastructure import (
    INFRASTRUCTURE_INSTRUCTION,
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
