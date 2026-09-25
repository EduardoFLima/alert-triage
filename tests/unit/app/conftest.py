"""Fixtures for the tests of the composition root."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest

from alert_triage.app import composition
from alert_triage.investigation.adapters.datadog.guides import DatadogGuide


@dataclass
class GuideFetch:
    """Stands in for reading the platform's guides, which would reach the network."""

    guides: tuple[DatadogGuide, ...] = ()
    asked: list[tuple[Sequence[Any], Any]] = field(default_factory=list)

    def __call__(
        self, crew: Sequence[Any], deployment: Any
    ) -> tuple[DatadogGuide, ...]:
        """Answer with the guides, remembering who asked."""
        self.asked.append((crew, deployment))
        return self.guides


@pytest.fixture(autouse=True)
def guide_fetch(monkeypatch: pytest.MonkeyPatch) -> GuideFetch:
    """Every investigator built here reads its guides from this, not the platform."""
    fetch = GuideFetch()
    monkeypatch.setattr(composition, "fetch_guides", fetch)
    return fetch
