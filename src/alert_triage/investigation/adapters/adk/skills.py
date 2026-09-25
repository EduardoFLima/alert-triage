"""The platform's guides as the framework serves them, loaded on demand.

A specialist is offered the guides documenting its own tools, and only those.
Their names and descriptions are in its prompt; a guide's text reaches it when
it asks for that guide, and a name it was not offered is refused, because the
toolset serving it does not hold that guide.

Loading a guide is not a retrieval. The toolset is in no declaration, so the
callbacks that bound a specialist's calls and keep its evidence pass it
through: it spends no budget, is not citable, and cannot fail an investigation.
"""

from collections.abc import Iterable
from typing import Any

from google.adk.skills.models import Frontmatter, Resources, Skill
from google.adk.skills.prompt import format_skills_as_xml
from google.adk.tools.skill_toolset import SkillToolset

from alert_triage.investigation.adapters.datadog.guides import (
    DatadogGuide,
    guides_for,
    kebab_name,
)
from alert_triage.investigation.domain.specialist import Specialist

LOADS = ["load_skill", "load_skill_resource"]
"""What a specialist may do with its guides: read one, or read what one bundles.

Not list them, because the menu is already in its prompt; not run a script,
because a guide here is text to read, not code to execute.
"""

DESCRIPTION_LIMIT = 1024
"""The longest description the framework accepts for a skill.

Some the platform lists run longer — keyword lists for search, mostly — and a
guide is better offered with its description cut than not offered at all.
"""
REFERENCES = "references/"
"""Where the framework looks a reference up, and the prefix it strips to do so."""


def skill_from(guide: DatadogGuide) -> Skill:
    """The skill the framework serves a guide as.

    Args:
        guide: The guide as the platform published it.

    Returns:
        A skill under the kebab-case form of the guide's name, holding its text
        and its references, each under its path beneath ``references/``.
    """
    return Skill(
        frontmatter=Frontmatter(
            name=kebab_name(guide.name), description=_described(guide)
        ),
        instructions=guide.text,
        resources=Resources(
            references={
                path.removeprefix(REFERENCES): text
                for path, text in guide.references.items()
            }
        ),
    )


def _described(guide: DatadogGuide) -> str:
    """The guide's description, within the framework's limit and never empty."""
    description = guide.description.strip() or f"Datadog's guide {guide.name}."
    if len(description) <= DESCRIPTION_LIMIT:
        return description
    return description[: DESCRIPTION_LIMIT - 1].rsplit(" ", 1)[0] + "…"


class _OnTheMenu(SkillToolset):
    """A skill toolset that names the skills it holds in the prompt itself.

    The framework adds that menu only when its own listing tool is absent, and
    it checks the tools it was built with rather than the ones its filter
    leaves. Filtered out, the listing is gone and the menu is never added, so
    an agent would be told it has skills and not which. This adds it.
    """

    async def process_llm_request(self, *, tool_context: Any, llm_request: Any) -> None:
        """Add the framework's own instruction, then the menu it leaves out."""
        await super().process_llm_request(
            tool_context=tool_context, llm_request=llm_request
        )
        menu: list[Frontmatter | Skill] = list(self.skills)
        llm_request.append_instructions([format_skills_as_xml(menu)])


def guidance_for(
    specialist: Specialist, guides: Iterable[DatadogGuide]
) -> SkillToolset | None:
    """The guides one specialist is offered, as a toolset it can load them from.

    Args:
        specialist: Whose tools decide which guides it is offered.
        guides: Every guide the platform published, as read when the run began.

    Returns:
        A toolset holding the guides documenting its tools, with its menu in
        the prompt and only loading permitted; ``None`` where it is offered
        none, so that it is told nothing of skills it does not have.
    """
    offered = guides_for(specialist, guides)
    if not offered:
        return None
    return _OnTheMenu([skill_from(guide) for guide in offered], tool_filter=LOADS)
