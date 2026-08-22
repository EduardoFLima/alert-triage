from alert_triage.adapters.adk.credentials import ApiKey, EnterprisePlatform
from alert_triage.adapters.adk.model import build_model


def test_the_model_reasons_under_the_name_it_was_given() -> None:
    assert build_model("gemini-2.5-flash", ApiKey("model-key")).model == (
        "gemini-2.5-flash"
    )


def test_the_model_is_built_to_authenticate_with_the_resolved_key() -> None:
    """What the run resolved, not what the SDK would have found for itself."""
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
    """No client, so no credential discovery and no network until an incident.

    ADK builds the client on first use; a run that finds no alerts should not
    have gone looking for credentials on the way to finding none.
    """
    reasoner = build_model("gemini-2.5-flash", ApiKey("model-key"))

    assert "api_client" not in reasoner.__dict__
