"""A reasoner is an instruction and a schema; a specialist is those plus its reach.

Keeping them separate types is what protects the specialist invariant. What an
APM agent *is* includes what it may ask, so a declaration with no toolsets is
not a specialist — and relaxing ``Specialist`` to admit one would erase the one
thing that makes a specialist declaration trustworthy.
"""

import pytest
from pydantic import BaseModel

from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.reasoner import Reasoner
from alert_triage.investigation.domain.specialist import Specialist


class _Answer(BaseModel):
    answer: str = ""


def test_a_reasoner_is_a_name_an_instruction_and_a_schema() -> None:
    reasoner = Reasoner(
        name="diagnostician",
        instruction="Decide which signals this incident needs.",
        output_schema=_Answer,
    )

    assert reasoner.name == "diagnostician"
    assert reasoner.output_schema is _Answer


def test_a_reasoner_takes_the_deployments_model_unless_it_names_one() -> None:
    assert (
        Reasoner(name="report", instruction="Word it.", output_schema=_Answer).model
        is None
    )
    assert (
        Reasoner(
            name="report",
            instruction="Word it.",
            output_schema=_Answer,
            model="gemini-2.5-pro",
        ).model
        == "gemini-2.5-pro"
    )


def test_a_reasoner_without_a_name_is_refused() -> None:
    with pytest.raises(ValueError, match="name"):
        Reasoner(name="  ", instruction="Reason.", output_schema=_Answer)


def test_a_reasoner_without_an_instruction_is_refused() -> None:
    """Without one it reasons about nothing, which is the specialist rule again."""
    with pytest.raises(ValueError, match="instruction"):
        Reasoner(name="diagnostician", instruction="   ", output_schema=_Answer)


def test_a_reasoner_needs_no_toolset_where_a_specialist_still_demands_one() -> None:
    Reasoner(name="report", instruction="Word it.", output_schema=_Answer)

    with pytest.raises(ValueError, match="no toolsets"):
        Specialist(
            name="logs_specialist",
            signal=Signal.LOGS,
            instruction="Look at the logs.",
            output_schema=_Answer,
            toolsets=(),
        )
