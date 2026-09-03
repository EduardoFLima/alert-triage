"""Every specialist may ask the platform how its own tools are queried.

The crew reaches five query grammars — the metric grammar, log search syntax,
SQL over two different virtual tables, and the Kubernetes filter syntax — and
this repository ever transcribed one of them, a rejection at a time. Datadog
publishes all five as skills on the same server the tools live on, so a
grammar is something a specialist looks up at the moment it needs it rather
than something a declaration carries a stale copy of.

Parameterised over the crew rather than written per specialist, so a
specialist added later inherits the check. Which skill answers which tool is
deliberately not asserted: naming a skill id here would be the transcription
this exists to remove, one indirection out.
"""

import pytest

from alert_triage.investigation.adapters.crew.roster import CREW
from alert_triage.investigation.adapters.datadog.dialect import (
    CONSULT_THE_PLATFORM,
    SKILL_LIST_TOOL,
    SKILL_LOAD_TOOL,
)
from alert_triage.investigation.domain.specialist import Specialist

CREWED = pytest.mark.parametrize(
    "specialist", CREW, ids=[specialist.name for specialist in CREW]
)


def _permitted(specialist: Specialist) -> set[str]:
    return {tool for toolset in specialist.toolsets for tool in toolset.tools}


@CREWED
def test_a_specialist_may_reach_the_platforms_own_guidance(
    specialist: Specialist,
) -> None:
    """Both halves: one lists what is published, the other fetches one."""
    assert {SKILL_LIST_TOOL, SKILL_LOAD_TOOL} <= _permitted(specialist)


@CREWED
def test_a_specialist_is_told_to_consult_it_before_writing_a_query(
    specialist: Specialist,
) -> None:
    """A tool it may reach and is never told to use is a tool it will not use."""
    assert SKILL_LIST_TOOL in specialist.instruction
    assert SKILL_LOAD_TOOL in specialist.instruction


@CREWED
def test_every_specialist_is_told_this_in_the_same_words(
    specialist: Specialist,
) -> None:
    """One account of it, so a correction reaches the whole crew at once."""
    assert CONSULT_THE_PLATFORM in specialist.instruction


@CREWED
def test_no_instruction_names_a_guide_the_platform_would_have_to_keep_stable(
    specialist: Specialist,
) -> None:
    """Naming a guide here is the staleness this replaced, one indirection out.

    The account publishes fifty-seven of them and renames them on its own
    schedule. A specialist that asks which exist survives that; one carrying a
    literal name fails silently the day it moves.
    """
    assert "datadog/" not in specialist.instruction
