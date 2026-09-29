from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest

from alert_triage.app import composition
from alert_triage.investigation.adapters.datadog.guides import DatadogGuide


@dataclass
class GuideFetch:
    guides: tuple[DatadogGuide, ...] = ()
    asked: list[tuple[Sequence[Any], Any]] = field(default_factory=list)

    def __call__(
        self, crew: Sequence[Any], deployment: Any
    ) -> tuple[DatadogGuide, ...]:
        self.asked.append((crew, deployment))
        return self.guides


@pytest.fixture(autouse=True)
def guide_fetch(monkeypatch: pytest.MonkeyPatch) -> GuideFetch:
    fetch = GuideFetch()
    monkeypatch.setattr(composition, "fetch_guides", fetch)
    return fetch
