from alert_triage.investigation.adapters.adk.reasoners.diagnostician import (
    DIAGNOSTICIAN,
    DIAGNOSTICIAN_INSTRUCTION,
    Diagnosed,
)
from alert_triage.investigation.contract import Confidence


def test_it_is_a_reasoner_that_takes_the_deployments_model() -> None:
    assert DIAGNOSTICIAN.name == "diagnostician"
    assert DIAGNOSTICIAN.model is None
    assert DIAGNOSTICIAN.output_schema is Diagnosed


def test_it_is_asked_to_consult_only_the_signals_this_incident_needs() -> None:
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "only the specialists" in lowered
    assert "every specialist" in lowered


def test_it_is_asked_to_choose_the_next_specialist_from_the_last_ones_answer() -> None:
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "what came back" in lowered
    assert "fixed order" in lowered


def test_it_may_go_back_to_a_specialist_with_a_narrower_question() -> None:
    """Re-asking is the manager's best move, not a loop to be avoided."""
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "narrower question" in lowered
    assert "more than once" in lowered


def test_it_is_told_the_questions_are_budgeted() -> None:
    from alert_triage.investigation.adapters.adk.consultation import MAX_CONSULTATIONS

    assert str(MAX_CONSULTATIONS) in DIAGNOSTICIAN_INSTRUCTION


def test_it_is_asked_to_reason_across_the_specialists_rather_than_restate_one() -> None:
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "across" in lowered
    assert "restate" in lowered


def test_it_is_asked_for_a_confidence_level_from_the_declared_set() -> None:
    for level in Confidence:
        assert level.value in DIAGNOSTICIAN_INSTRUCTION


def test_it_is_told_a_refused_consultation_is_not_a_quiet_specialist() -> None:
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "refused" in lowered
    assert "conclude on what you already have" in lowered


def test_it_is_forbidden_from_naming_evidence_it_was_not_shown() -> None:
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "do not invent" in lowered or "never invent" in lowered
    assert "specialists reported" in lowered


def test_it_is_told_a_hypothesis_needs_a_finding_under_it() -> None:
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "no findings" in lowered
    assert "say so" in lowered


def test_it_recommends_no_action() -> None:
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "do not recommend" in lowered
    assert "human" in lowered


def test_its_schema_offers_no_field_evidence_could_be_written_into() -> None:
    """It concludes over checked findings; it never carries evidence of its own."""
    fields = set(Diagnosed.model_fields)

    assert fields == {"hypothesis", "confidence"}


def test_its_schema_admits_only_the_declared_confidence_levels() -> None:
    import pytest
    from pydantic import ValidationError

    for level in Confidence:
        assert Diagnosed.model_validate(
            {"hypothesis": "something", "confidence": level.value}
        )

    with pytest.raises(ValidationError):
        Diagnosed.model_validate(
            {"hypothesis": "something", "confidence": "fairly sure"}
        )


def test_it_is_told_one_specialist_is_rarely_the_whole_picture() -> None:
    """The framework injects "call set_model_response after any tools you need".

    Read beside an instruction that says stop as soon as you can, a model takes
    the first answer it gets and finalises. So the instruction has to say what
    "enough" means rather than leave it to be inferred.
    """
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "one specialist" in lowered
    assert "rarely" in lowered


def test_it_is_told_to_weigh_every_signal_before_concluding() -> None:
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "each signal" in lowered
    assert "before you conclude" in lowered


def test_it_is_told_not_to_finalise_while_a_signal_is_still_worth_asking() -> None:
    lowered = DIAGNOSTICIAN_INSTRUCTION.lower()

    assert "final answer" in lowered
    assert "do not give your final answer" in lowered
