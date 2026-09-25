"""The platform's guides, read once as a run starts and held for it in memory.

Read here rather than on the first investigation so that the reading is outside
every investigation's bounds: a slow platform costs the run a late start, not an
incident its tool budget. Only guides some specialist in the crew is offered are
kept, and only their references are read.

A run whose guides cannot be read still runs. Guidance helps a specialist write
a query; it is not evidence, and its absence is no reason to investigate less.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING

from alert_triage.investigation.adapters.adk.agent import Deployment, connection_for
from alert_triage.investigation.adapters.datadog.guides import (
    DatadogGuide,
    ListedGuide,
    guide_arguments,
    guides_for,
    listed_guides,
    listing_arguments,
    reference_arguments,
)
from alert_triage.investigation.adapters.datadog.mcp import DATADOG
from alert_triage.investigation.adapters.datadog.tools import LIST_SKILLS, LOAD_SKILL
from alert_triage.investigation.domain.specialist import Specialist, Toolset

if TYPE_CHECKING:
    from mcp import ClientSession

_log = logging.getLogger(__name__)

Pause = Callable[[float], Awaitable[None]]
"""How to wait before asking again; a test hands in one that does not."""

LOAD_ATTEMPTS = 3
REFUSED_LOAD_PAUSE_SECONDS = 10.0
"""How a refused load is met.

The server refuses a burst — on the account first read, about forty-five loads
in quick succession — with an error result rather than a delay, and a pause of
seconds is enough for it to answer again.
"""


class _RefusedError(Exception):
    """The platform answered a guide call with an error."""


def fetch_guides(
    crew: Sequence[Specialist],
    deployment: Deployment,
    pause: Pause = asyncio.sleep,
) -> tuple[DatadogGuide, ...]:
    """Every guide some specialist in the crew is offered, with its references.

    Args:
        crew: The specialists this run may consult; whose tools decide which
            guides are kept, and whose toolsets decide which the platform shows.
        deployment: Where the platform is, and how long one call may take.
        pause: How to wait before asking again after a refusal.

    Returns:
        The guides, in the order the platform listed them. None where the crew
        reaches no Datadog toolset, or where the platform could not be read —
        which is logged once, as a warning, rather than raised: whatever went
        wrong, the run is better investigating unguided than not at all.
    """
    toolsets = sorted(
        {
            toolset.name
            for specialist in crew
            for toolset in specialist.toolsets
            if toolset.provider == DATADOG
        }
    )
    if not toolsets:
        return ()
    try:
        return asyncio.run(_fetch(crew, deployment, ",".join(toolsets), pause))
    except Exception as unread:
        _log.warning(
            "The platform's guides could not be read (%s); investigating with "
            "none offered",
            unread,
        )
        return ()


async def _fetch(
    crew: Sequence[Specialist],
    deployment: Deployment,
    toolsets: str,
    pause: Pause,
) -> tuple[DatadogGuide, ...]:
    """Read the listing, each guide, and the references of those offered."""
    from google.adk.tools.mcp_tool.mcp_session_manager import MCPSessionManager

    manager = MCPSessionManager(
        connection_params=connection_for(
            Toolset(DATADOG, toolsets, (LIST_SKILLS.name, LOAD_SKILL.name)),
            deployment,
        )
    )
    bound = timedelta(seconds=deployment.breakers.mcp_call_timeout_seconds)
    try:
        session = await manager.create_session()
        listing = await _call(session, LIST_SKILLS.name, listing_arguments(), bound)
        loaded = [
            (listed, guide)
            for listed in listed_guides(listing)
            if (guide := await _guide(session, listed, bound, pause)) is not None
        ]
        offered = {
            guide.name
            for specialist in crew
            for guide in guides_for(specialist, [guide for _, guide in loaded])
        }
        return tuple(
            [
                await _with_references(session, guide, listed, bound, pause)
                for listed, guide in loaded
                if guide.name in offered
            ]
        )
    finally:
        await manager.close()


async def _guide(
    session: "ClientSession",
    listed: ListedGuide,
    bound: timedelta,
    pause: Pause,
) -> DatadogGuide | None:
    """One guide's text, or ``None`` where the platform keeps refusing it."""
    text = await _patiently(
        session, guide_arguments(listed.name), bound, pause, listed.name
    )
    if text is None:
        return None
    return DatadogGuide(name=listed.name, description=listed.description, text=text)


async def _with_references(
    session: "ClientSession",
    guide: DatadogGuide,
    listed: ListedGuide,
    bound: timedelta,
    pause: Pause,
) -> DatadogGuide:
    """The guide with every reference it bundles that the platform would give."""
    references: dict[str, str] = {}
    for path in listed.references:
        text = await _patiently(
            session,
            reference_arguments(guide.name, path),
            bound,
            pause,
            f"{guide.name} {path}",
        )
        if text is not None:
            references[path] = text
    return replace(guide, references=references)


async def _patiently(
    session: "ClientSession",
    arguments: dict[str, object],
    bound: timedelta,
    pause: Pause,
    what: str,
) -> str | None:
    """A load, asked again after a pause while refused, up to the attempts allowed."""
    for attempt in range(1, LOAD_ATTEMPTS + 1):
        try:
            return await _call(session, LOAD_SKILL.name, arguments, bound)
        except _RefusedError as refused:
            if attempt == LOAD_ATTEMPTS:
                _log.warning(
                    "Guide %s left out: the platform refused it %d times (%s)",
                    what,
                    LOAD_ATTEMPTS,
                    refused,
                )
                return None
            await pause(REFUSED_LOAD_PAUSE_SECONDS)
    return None


async def _call(
    session: "ClientSession",
    tool: str,
    arguments: dict[str, object],
    bound: timedelta,
) -> str:
    """One call's text, bounded; an error result is raised as a refusal."""
    from mcp.types import TextContent

    result = await session.call_tool(tool, arguments, read_timeout_seconds=bound)
    text = "\n".join(
        item.text for item in result.content if isinstance(item, TextContent)
    )
    if result.isError:
        raise _RefusedError(text[:200])
    return text
