"""A guide the platform published becomes a skill the framework can serve.

The framework is strict where the platform is not: a skill's name must be
kebab-case, its description at most 1024 characters and never empty, and a
reference is looked up by its path beneath ``references/``.
"""

from alert_triage.investigation.adapters.adk.guides import skill_from
from alert_triage.investigation.adapters.datadog.guides import DatadogGuide

KUBERNETES = DatadogGuide(
    name="datadog/kubernetes",
    description="Load this skill when inspecting Kubernetes resources.",
    text="# Kubernetes\n\n### search_datadog_k8s_resources",
    references={"references/query-syntax.md": "Filter on kube_namespace."},
)


def test_a_skill_is_named_as_the_framework_requires() -> None:
    assert skill_from(KUBERNETES).name == "datadog-kubernetes"


def test_a_skill_says_what_the_listing_said_and_holds_the_guide() -> None:
    skill = skill_from(KUBERNETES)

    assert skill.description == KUBERNETES.description
    assert skill.instructions == KUBERNETES.text


def test_a_reference_is_found_by_the_path_the_listing_gave_it() -> None:
    """The framework strips ``references/`` from the path the model asks for."""
    skill = skill_from(KUBERNETES)

    assert skill.resources.get_reference("query-syntax.md") == (
        "Filter on kube_namespace."
    )


def test_a_description_too_long_for_the_framework_is_shortened_at_a_word() -> None:
    long = DatadogGuide(
        name="datadog/dbm-clickhouse",
        description="Trigger keywords: " + "mergetree, " * 200,
        text="# ClickHouse",
    )

    description = skill_from(long).description

    assert len(description) <= 1024
    assert description.endswith("mergetree,…")


def test_a_guide_listed_without_a_description_is_still_served() -> None:
    bare = DatadogGuide(name="generic", description="", text="# Steering guide")

    assert skill_from(bare).description == "Datadog's guide generic."
