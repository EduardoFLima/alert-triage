from alert_triage.investigation.adapters.adk.credentials import (
    ApiKey,
    EnterprisePlatform,
)
from alert_triage.investigation.adapters.adk.model import build_model


def test_the_model_reasons_under_the_name_it_was_given() -> None:
    assert build_model("gemini-2.5-flash", ApiKey("model-key")).model == (
        "gemini-2.5-flash"
    )


def test_the_model_is_built_to_authenticate_with_the_resolved_key() -> None:
    reasoner = build_model("gemini-2.5-flash", ApiKey("model-key"))

    assert reasoner.client_kwargs == {"api_key": "model-key"}


def test_the_model_is_built_against_the_platform_that_was_resolved() -> None:
    access = EnterprisePlatform(project="triage-prod", location="europe-west4")

    reasoner = build_model("gemini-2.5-flash", access)

    assert reasoner.client_kwargs == {
        "enterprise": True,
        "project": "triage-prod",
        "location": "europe-west4",
    }


def test_building_the_model_reaches_nothing() -> None:
    """ADK builds the client on first use, so no-alert runs discover no credentials."""
    reasoner = build_model("gemini-2.5-flash", ApiKey("model-key"))

    assert "api_client" not in reasoner.__dict__
