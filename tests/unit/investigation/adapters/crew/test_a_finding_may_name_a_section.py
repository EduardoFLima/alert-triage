"""A specialist may say which part of the service a finding concerns, from a set.

The bound is what makes this admissible at all: a section outside the set is
rejected by the schema the model answers through, rather than carried into an
address a reader would follow.
"""

import pytest
from pydantic import ValidationError

from alert_triage.investigation.adapters.crew.roster import CREW
from alert_triage.investigation.domain.specialist import Specialist


def _reported(**finding: object) -> dict[str, object]:
    return {
        "findings": [
            {"observation": "checkout was rolled out", "occurrences": 1}
            | {"cites": ["call-1"]}
            | finding
        ]
    }


@pytest.mark.parametrize("specialist", CREW, ids=[s.name for s in CREW])
def test_a_specialist_may_name_a_section_from_the_set(specialist: Specialist) -> None:
    reported = specialist.output_schema.model_validate(
        _reported(section="infrastructure")
    )

    assert reported.model_dump()["findings"][0]["section"] == "infrastructure"


@pytest.mark.parametrize("specialist", CREW, ids=[s.name for s in CREW])
def test_a_section_outside_the_set_does_not_validate(specialist: Specialist) -> None:
    with pytest.raises(ValidationError):
        specialist.output_schema.model_validate(_reported(section="the graphs tab"))


@pytest.mark.parametrize("specialist", CREW, ids=[s.name for s in CREW])
def test_a_specialist_need_name_no_section(specialist: Specialist) -> None:
    reported = specialist.output_schema.model_validate(_reported())

    assert reported.model_dump()["findings"][0]["section"] is None
