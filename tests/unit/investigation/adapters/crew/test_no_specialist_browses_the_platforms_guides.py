"""No specialist browses the platform's guides; it is offered the ones it needs.

Browsing let a specialist read about tools its declaration does not permit, and
then try to call them, and every list or load spent its tool budget and was
kept as evidence. The guides documenting its own tools now reach it through the
framework instead, read once when the run starts, so neither of the platform's
own guide tools belongs in a declaration or an instruction.

Every declaration counts, Preview included: a declaration an account with
Preview access gets must not browse either.
"""

import pytest

from alert_triage.investigation.adapters.crew.specialists.apm import apm_specialist
from alert_triage.investigation.adapters.crew.specialists.infrastructure import (
    INFRASTRUCTURE_SPECIALIST,
)
from alert_triage.investigation.adapters.crew.specialists.logs import (
    LOGS_SPECIALIST,
)
from alert_triage.investigation.adapters.crew.specialists.trace import (
    trace_specialist,
)
from alert_triage.investigation.adapters.datadog.tools import LIST_SKILLS, LOAD_SKILL
from alert_triage.investigation.domain.specialist import Specialist

EVERY_DECLARATION = (
    LOGS_SPECIALIST,
    INFRASTRUCTURE_SPECIALIST,
    apm_specialist(preview=False),
    apm_specialist(preview=True),
    trace_specialist(preview=False),
    trace_specialist(preview=True),
)

DECLARED = pytest.mark.parametrize(
    "specialist",
    EVERY_DECLARATION,
    ids=[
        f"{specialist.name}-{index}"
        for index, specialist in enumerate(EVERY_DECLARATION)
    ],
)

GUIDE_TOOLS = (LIST_SKILLS.name, LOAD_SKILL.name)


def _permitted(specialist: Specialist) -> set[str]:
    return {tool for toolset in specialist.toolsets for tool in toolset.tools}


@DECLARED
def test_no_specialist_may_reach_the_platforms_guide_tools(
    specialist: Specialist,
) -> None:
    assert _permitted(specialist).isdisjoint(GUIDE_TOOLS)


@DECLARED
def test_no_instruction_tells_a_specialist_to_browse_the_guides(
    specialist: Specialist,
) -> None:
    """Its menu of guides is added by the framework, not written here."""
    for tool in GUIDE_TOOLS:
        assert tool not in specialist.instruction


@DECLARED
def test_no_instruction_names_a_guide_the_platform_would_have_to_keep_stable(
    specialist: Specialist,
) -> None:
    """Which guides a specialist is offered follows from its tools, not its prose."""
    assert "datadog/" not in specialist.instruction
