"""What a specialist may reach, checked against what it is told it may reach.

The likeliest mistake in a new declaration is a copy-paste: an instruction that
names a tool the declaration never permitted, so the model asks for something
the filter refuses, or a permitted tool no instruction mentions, so nothing ever
calls it. Neither shows up in a fake, and both are cheap to catch here.

Parameterised over the crew rather than written per specialist, so a specialist
added later inherits the check without anyone remembering to extend it.
"""

import re

import pytest

from alert_triage.investigation.adapters.adk.crew import CREW
from alert_triage.investigation.domain.specialist import Specialist

QUOTED_IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")
"""What a tool name looks like, and what a query example never does.

An instruction quotes both its tools and the platform's query dialect. The
dialect carries punctuation a bare identifier does not — colons, braces, dots
— which is what tells the two apart without a catalogue to check against.
"""

CREWED = pytest.mark.parametrize(
    "specialist", CREW, ids=[specialist.name for specialist in CREW]
)


def _permitted(specialist: Specialist) -> set[str]:
    return {tool for toolset in specialist.toolsets for tool in toolset.tools}


def _tools_named_in(instruction: str) -> set[str]:
    return {
        quoted
        for quoted in re.findall(r"`([^`]+)`", instruction)
        if QUOTED_IDENTIFIER.fullmatch(quoted)
    }


@CREWED
def test_every_tool_a_specialist_permits_is_named_in_its_instruction(
    specialist: Specialist,
) -> None:
    """A permitted tool no instruction mentions is a tool nothing will call."""
    assert _permitted(specialist) <= _tools_named_in(specialist.instruction)


@CREWED
def test_every_tool_an_instruction_names_is_one_the_declaration_permits(
    specialist: Specialist,
) -> None:
    """A tool the filter refuses is a retrieval the model cannot make."""
    assert _tools_named_in(specialist.instruction) <= _permitted(specialist)


@CREWED
def test_every_specialist_takes_the_deployments_model_unless_configured(
    specialist: Specialist,
) -> None:
    """Which specialist deserves a stronger model is a question for evidence."""
    assert specialist.model is None
