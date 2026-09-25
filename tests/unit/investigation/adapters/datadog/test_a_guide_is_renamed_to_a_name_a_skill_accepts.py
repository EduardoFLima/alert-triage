"""A Datadog guide's name, turned into one an ADK skill accepts.

ADK requires a skill name in lowercase kebab-case; the platform names its
guides as it likes. The model only ever sees the renamed one, so nothing maps
it back.
"""

import pytest
from google.adk.skills.models import Frontmatter

from alert_triage.investigation.adapters.datadog.guides import kebab_name


@pytest.mark.parametrize(
    ("published", "renamed"),
    (
        ("datadog/metrics", "datadog-metrics"),
        ("Datadog Logs_Search", "datadog-logs-search"),
        ("/datadog//k8s/", "datadog-k8s"),
        ("already-kebab", "already-kebab"),
    ),
)
def test_a_published_name_becomes_kebab_case(published: str, renamed: str) -> None:
    assert kebab_name(published) == renamed


def test_the_renamed_guide_is_one_adk_accepts() -> None:
    Frontmatter(name=kebab_name("datadog/metrics"), description="Metrics.")
