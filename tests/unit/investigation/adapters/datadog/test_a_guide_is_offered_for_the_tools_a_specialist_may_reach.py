"""A specialist is offered the platform's guides that concern its own tools.

Which guides concern it follows from the tools its declaration already names,
so there is no list of guide names to keep by hand: widening a declaration
widens its guidance, and a guide the platform renames is still found.
"""

from pydantic import BaseModel

from alert_triage.investigation.adapters.datadog.guides import (
    DatadogGuide,
    guides_for,
)
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset


class _Report(BaseModel):
    summary: str


def _specialist(*toolsets: Toolset) -> Specialist:
    return Specialist(
        name="infrastructure",
        signal=Signal.INFRASTRUCTURE,
        instruction="Look at the metrics.",
        output_schema=_Report,
        toolsets=toolsets,
    )


def _guide(name: str, text: str) -> DatadogGuide:
    return DatadogGuide(name=name, description=f"About {name}.", text=text)


METRICS = _specialist(Toolset("datadog", "core", ("get_datadog_metric",)))


def test_a_guide_naming_a_permitted_tool_is_offered() -> None:
    guide = _guide("datadog/metrics", "Call `get_datadog_metric` with a query.")

    assert guides_for(METRICS, (guide,)) == (guide,)


def test_a_guide_naming_only_other_tools_is_not_offered() -> None:
    """Reading about a tool it cannot call is what sends a model to call it."""
    guide = _guide("datadog/logs", "Call `search_datadog_logs` with a log query.")

    assert guides_for(METRICS, (guide,)) == ()


def test_a_tool_named_inside_a_longer_one_is_not_a_match() -> None:
    """`get_datadog_metric` is a prefix of `get_datadog_metric_context`."""
    guide = _guide("datadog/context", "Call `get_datadog_metric_context` for tags.")

    assert guides_for(METRICS, (guide,)) == ()


def test_a_specialist_with_two_toolsets_is_offered_guides_for_either() -> None:
    specialist = _specialist(
        Toolset("datadog", "core", ("get_datadog_metric",)),
        Toolset("datadog", "kubernetes", ("search_datadog_k8s_resources",)),
    )
    metrics = _guide("datadog/metrics", "Use `get_datadog_metric`.")
    workloads = _guide("datadog/k8s", "Use `search_datadog_k8s_resources`.")

    assert guides_for(specialist, (metrics, workloads)) == (metrics, workloads)
