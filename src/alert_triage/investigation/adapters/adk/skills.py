"""Guides are load-only ADK skills; reading them spends no investigation budget."""

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
"""No listing tool: the menu is already in the prompt, and guides are text."""

DESCRIPTION_LIMIT = 1024
"""Some guide descriptions exceed ADK limits; cutting beats omitting."""
REFERENCES = "references/"


def skill_from(guide: DatadogGuide) -> Skill:
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
    description = guide.description.strip() or f"Datadog's guide {guide.name}."
    if len(description) <= DESCRIPTION_LIMIT:
        return description
    return description[: DESCRIPTION_LIMIT - 1].rsplit(" ", 1)[0] + "…"


class _OnTheMenu(SkillToolset):
    """ADK omits the skills menu when its listing tool exists before filtering.

    This toolset appends the menu after filtering removes that tool.
    """

    async def process_llm_request(self, *, tool_context: Any, llm_request: Any) -> None:
        await super().process_llm_request(
            tool_context=tool_context, llm_request=llm_request
        )
        menu: list[Frontmatter | Skill] = list(self.skills)
        llm_request.append_instructions([format_skills_as_xml(menu)])


def guidance_for(
    specialist: Specialist, guides: Iterable[DatadogGuide]
) -> SkillToolset | None:
    offered = guides_for(specialist, guides)
    if not offered:
        return None
    return _OnTheMenu([skill_from(guide) for guide in offered], tool_filter=LOADS)
