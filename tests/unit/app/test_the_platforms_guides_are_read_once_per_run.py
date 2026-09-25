"""An investigator is built with the platform's guides, read once as it is built."""

from typing import Any

import pytest

from alert_triage.app import composition
from alert_triage.configuration.settings import Investigation
from alert_triage.investigation.adapters.datadog.guides import DatadogGuide
from alert_triage.triage.adapters.datadog.connection import DatadogConnection

METRICS = DatadogGuide(
    name="datadog/metrics",
    description="Load this skill when querying metrics.",
    text="### get_datadog_metric",
)


def _build(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    deployments: list[Any] = []

    def _capture(deployment: Any) -> Any:
        deployments.append(deployment)
        return lambda *args: {}

    monkeypatch.setattr(composition, "run_with_adk", _capture)
    composition.build_investigator(
        {"GOOGLE_API_KEY": "model-key"},
        DatadogConnection(site="datadoghq.eu", api_key="api", app_key="app"),
        Investigation(),
    )
    return deployments


def test_the_guides_are_read_once_for_the_crew_being_built(
    monkeypatch: pytest.MonkeyPatch, guide_fetch: Any
) -> None:
    _build(monkeypatch)

    assert len(guide_fetch.asked) == 1
    crew, _ = guide_fetch.asked[0]
    assert {specialist.name for specialist in crew} >= {"logs_specialist"}


def test_the_deployment_the_agents_are_built_from_holds_the_guides(
    monkeypatch: pytest.MonkeyPatch, guide_fetch: Any
) -> None:
    guide_fetch.guides = (METRICS,)

    deployments = _build(monkeypatch)

    assert deployments[0].guides == (METRICS,)


def test_the_guides_are_read_over_the_platform_the_crew_reaches(
    monkeypatch: pytest.MonkeyPatch, guide_fetch: Any
) -> None:
    _build(monkeypatch)

    _, deployment = guide_fetch.asked[0]
    assert deployment.platforms["datadog"].endpoint == "https://mcp.datadoghq.eu/v1/mcp"
