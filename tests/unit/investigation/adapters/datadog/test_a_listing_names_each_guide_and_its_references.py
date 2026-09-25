"""The listing says which guides exist, what each covers, and what it bundles.

The shape is the one the real server returns with ``include_header``: a line
per guide, its related guides in a trailing parenthesis, and its bundled
references on an indented line beneath.
"""

from alert_triage.investigation.adapters.datadog.guides import (
    ListedGuide,
    listed_guides,
)

LISTING = """\
- **datadog/metrics**: Load this skill when querying metrics. (related: datadog/querying-patterns)
- **datadog/kubernetes**: Load this skill for Kubernetes resources. (related: datadog/services-and-infrastructure)
  Resources: references/query-syntax.md, references/sorting-fields.md
- **datadog/cases**: "Load this skill for Case Management." (related: datadog/incidents-and-alerting)
- **generic**: The steering guide.
"""  # noqa: E501


def test_each_guide_is_listed_with_what_it_covers() -> None:
    assert listed_guides(LISTING)[0] == ListedGuide(
        name="datadog/metrics",
        description="Load this skill when querying metrics.",
        references=(),
    )


def test_a_guides_bundled_references_are_listed_with_it() -> None:
    assert listed_guides(LISTING)[1].references == (
        "references/query-syntax.md",
        "references/sorting-fields.md",
    )


def test_a_quoted_description_is_unquoted() -> None:
    assert (
        listed_guides(LISTING)[2].description == "Load this skill for Case Management."
    )


def test_a_guide_with_no_related_guides_keeps_its_whole_description() -> None:
    assert listed_guides(LISTING)[3] == ListedGuide(
        name="generic", description="The steering guide.", references=()
    )


def test_nothing_else_in_the_listing_is_taken_for_a_guide() -> None:
    assert len(listed_guides(f"Available guides:\n\n{LISTING}\n")) == 4
