"""Guides are matched by tool headings, so platform renames do not matter."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from alert_triage.investigation.domain.specialist import Specialist


@dataclass(frozen=True)
class DatadogGuide:
    name: str
    description: str
    text: str
    references: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ListedGuide:
    name: str
    description: str
    references: tuple[str, ...]


TELEMETRY = {
    "intent": (
        "Reading the platform's guides once at startup, to offer each "
        "investigating agent those documenting its own tools."
    )
}
"""Datadog refuses guide-tool calls without telemetry."""


def listing_arguments() -> dict[str, object]:
    return {"include_header": True, "telemetry": TELEMETRY}


def guide_arguments(name: str) -> dict[str, object]:
    return {"skill_name": name, "telemetry": TELEMETRY}


def reference_arguments(name: str, path: str) -> dict[str, object]:
    return {"skill_name": name, "resource_path": path, "telemetry": TELEMETRY}


_LISTED = re.compile(
    r"^- \*\*(?P<name>[^*]+)\*\*: (?P<description>.*?)(?: \(related: [^)]*\))?$"
    r"(?:\n  Resources: (?P<references>.*)$)?",
    re.MULTILINE,
)


def listed_guides(listing: str) -> tuple[ListedGuide, ...]:
    """Drop related guides because this adapter never follows them."""
    return tuple(
        ListedGuide(
            name=match["name"],
            description=match["description"].strip().strip('"'),
            references=tuple(
                path.strip()
                for path in (match["references"] or "").split(",")
                if path.strip()
            ),
        )
        for match in _LISTED.finditer(listing)
    )


def guides_for(
    specialist: Specialist, guides: Iterable[DatadogGuide]
) -> tuple[DatadogGuide, ...]:
    permitted = {tool for toolset in specialist.toolsets for tool in toolset.tools}
    return tuple(guide for guide in guides if _documents_any(guide.text, permitted))


def _documents_any(text: str, tools: Iterable[str]) -> bool:
    """Match headings, not passing mentions; tool names also nest."""
    return any(
        re.search(
            rf"^#+[ \t][^\n]*(?<![\w-]){re.escape(tool)}(?![\w-])", text, re.MULTILINE
        )
        for tool in tools
    )


def kebab_name(published: str) -> str:
    """ADK skills accept only lowercase kebab-case names."""
    return re.sub(r"[^a-z0-9]+", "-", published.lower()).strip("-")
