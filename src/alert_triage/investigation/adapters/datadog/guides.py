"""The guides Datadog publishes to how its own tools are queried, and who gets which.

A guide concerns a specialist when it documents a tool that specialist may
call, under a heading of its own. That rule is the whole of the matching: no
list of guide names is kept here or anywhere, so a guide the platform renames is
still found, and a declaration widened to a new tool brings that tool's guide
with it.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from alert_triage.investigation.domain.specialist import Specialist


@dataclass(frozen=True)
class DatadogGuide:
    """One guide, as the platform published it.

    Attributes:
        name: What the platform calls it.
        description: What the listing says it covers.
        text: The guide itself.
    """

    name: str
    description: str
    text: str


def guides_for(
    specialist: Specialist, guides: Iterable[DatadogGuide]
) -> tuple[DatadogGuide, ...]:
    """The guides documenting a tool this specialist's declaration permits.

    Args:
        specialist: Whose tools decide.
        guides: Every guide the platform published.

    Returns:
        Those with a heading for at least one permitted tool, in the order
        given.
    """
    permitted = {tool for toolset in specialist.toolsets for tool in toolset.tools}
    return tuple(guide for guide in guides if _documents_any(guide.text, permitted))


def _documents_any(text: str, tools: Iterable[str]) -> bool:
    """Whether the text has a heading for one of the tools, as a whole word.

    A heading rather than any mention, because playbooks for other products
    name common tools in passing — offered on a mention, every specialist was
    handed dozens of guides it had no use for. Whole-word because tool names
    nest: ``get_datadog_metric`` is a prefix of ``get_datadog_metric_context``,
    and a guide to the second is not one to the first.
    """
    return any(
        re.search(
            rf"^#+[ \t][^\n]*(?<![\w-]){re.escape(tool)}(?![\w-])", text, re.MULTILINE
        )
        for tool in tools
    )


def kebab_name(published: str) -> str:
    """A guide's name as lowercase kebab-case, the only form a skill may take.

    The platform names guides as it likes — ``datadog/metrics``, say — and the
    framework serving them refuses anything but kebab-case. Every run of other
    characters becomes one hyphen; the model only ever sees this form.

    Args:
        published: What the platform calls the guide.

    Returns:
        The same name, lowercased, with each run of anything but a letter or
        digit turned into a single hyphen and none left at either end.
    """
    return re.sub(r"[^a-z0-9]+", "-", published.lower()).strip("-")
