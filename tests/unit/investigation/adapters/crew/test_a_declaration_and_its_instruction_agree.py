import re
from typing import cast, get_args

import pytest
from pydantic import BaseModel

from alert_triage.investigation.adapters.crew.roster import CREW
from alert_triage.investigation.adapters.crew.specialists.apm import APM_SPECIALIST
from alert_triage.investigation.adapters.crew.specialists.infrastructure import (
    INFRASTRUCTURE_SPECIALIST,
)
from alert_triage.investigation.adapters.crew.specialists.trace import (
    TRACE_SPECIALIST,
)
from alert_triage.investigation.adapters.datadog.dialect import (
    AN_EMPTY_ANSWER,
    IN_THE_ENVIRONMENT,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING
from alert_triage.investigation.domain.specialist import Specialist

QUOTED_IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")
CREWED = pytest.mark.parametrize(
    "specialist", CREW, ids=[specialist.name for specialist in CREW]
)

DECLARED_ANYWHERE = {
    tool for one in CREW for toolset in one.toolsets for tool in toolset.tools
}


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
    assert _permitted(specialist) <= _tools_named_in(specialist.instruction)


@CREWED
def test_every_tool_an_instruction_names_is_one_the_declaration_permits(
    specialist: Specialist,
) -> None:
    named = _tools_named_in(specialist.instruction) & DECLARED_ANYWHERE

    assert named <= _permitted(specialist)


@CREWED
def test_every_specialist_takes_the_deployments_model_unless_configured(
    specialist: Specialist,
) -> None:
    assert specialist.model is None


@CREWED
def test_every_specialist_bounds_the_examples_it_asks_for(
    specialist: Specialist,
) -> None:
    assert str(MAX_EXAMPLES_PER_FINDING) in specialist.instruction


@CREWED
def test_every_specialist_forbids_naming_a_root_cause(
    specialist: Specialist,
) -> None:
    assert "root cause" in specialist.instruction.lower()


@CREWED
def test_every_specialist_response_is_a_list_of_findings(
    specialist: Specialist,
) -> None:
    assert set(specialist.output_schema.model_fields) == {"findings"}


def _finding_schema(specialist: Specialist) -> type[BaseModel]:
    (schema,) = get_args(specialist.output_schema.model_fields["findings"].annotation)
    return cast(type[BaseModel], schema)


@CREWED
def test_every_specialist_finding_cites_evidence_without_storing_it(
    specialist: Specialist,
) -> None:
    assert set(_finding_schema(specialist).model_fields) == {
        "observation",
        "occurrences",
        "cites",
        "section",
    }


EMPTY_IS_AMBIGUOUS = pytest.mark.parametrize(
    "specialist",
    (APM_SPECIALIST, TRACE_SPECIALIST, INFRASTRUCTURE_SPECIALIST),
    ids=lambda specialist: specialist.name,
)


@EMPTY_IS_AMBIGUOUS
def test_an_empty_answer_is_explained_in_the_same_words_everywhere(
    specialist: Specialist,
) -> None:
    assert AN_EMPTY_ANSWER in specialist.instruction


@CREWED
def test_every_specialist_is_told_to_stay_inside_the_environment(
    specialist: Specialist,
) -> None:
    assert IN_THE_ENVIRONMENT in specialist.instruction
