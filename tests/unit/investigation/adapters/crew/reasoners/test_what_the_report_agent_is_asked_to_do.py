from alert_triage.investigation.adapters.crew.reasoners.report import (
    REPORT_INSTRUCTION,
    REPORT_WRITER,
    Worded,
)


def test_it_is_a_reasoner_that_takes_the_deployments_model() -> None:
    assert REPORT_WRITER.name == "report_writer"
    assert REPORT_WRITER.model is None
    assert REPORT_WRITER.output_schema is Worded


def test_it_is_asked_for_a_single_line_headline() -> None:
    lowered = REPORT_INSTRUCTION.lower()

    assert "one line" in lowered
    assert "subject" in lowered


def test_it_is_asked_to_explain_what_the_hypothesis_rests_on() -> None:
    lowered = REPORT_INSTRUCTION.lower()

    assert "rests on" in lowered
    assert "worth checking" in lowered


def test_it_is_forbidden_from_reproducing_the_evidence() -> None:
    """The evidence is rendered from what was retrieved, beneath what it writes."""
    lowered = REPORT_INSTRUCTION.lower()

    assert "do not reproduce" in lowered
    assert "beneath" in lowered


def test_it_is_forbidden_from_stating_a_confidence_the_diagnosis_did_not() -> None:
    lowered = REPORT_INSTRUCTION.lower()

    assert "confidence" in lowered
    assert "do not raise" in lowered or "do not change" in lowered


def test_it_recommends_no_action() -> None:
    assert "do not recommend" in REPORT_INSTRUCTION.lower()


def test_its_schema_offers_a_headline_and_a_narrative_and_no_field_for_evidence() -> (
    None
):
    assert set(Worded.model_fields) == {"headline", "narrative"}
