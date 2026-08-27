import pytest

from alert_triage.configuration.port import ConfigError
from alert_triage.investigation.adapters.adk.credentials import (
    ALTERNATE_API_KEY_VARIABLE,
    API_KEY_VARIABLE,
    ENTERPRISE_VARIABLE,
    LOCATION_VARIABLE,
    PROJECT_VARIABLE,
    ApiKey,
    EnterprisePlatform,
    client_arguments,
    resolve_model_access,
)


def test_an_api_key_deployment_resolves_to_the_key() -> None:
    access = resolve_model_access(env={API_KEY_VARIABLE: "model-key"})

    assert access == ApiKey("model-key")


def test_the_sdks_own_alternate_variable_is_accepted() -> None:
    """An operator who already exports GEMINI_API_KEY exports nothing new."""
    access = resolve_model_access(env={ALTERNATE_API_KEY_VARIABLE: "model-key"})

    assert access == ApiKey("model-key")


def test_the_primary_variable_wins_over_the_alternate() -> None:
    """As the SDK itself resolves them, so a run reasons on the key it reports."""
    access = resolve_model_access(
        env={API_KEY_VARIABLE: "primary", ALTERNATE_API_KEY_VARIABLE: "alternate"}
    )

    assert access == ApiKey("primary")


def test_the_environment_is_read_from_the_process_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENTERPRISE_VARIABLE)
    monkeypatch.setenv(API_KEY_VARIABLE, "model-key")

    assert resolve_model_access() == ApiKey("model-key")


def test_an_enterprise_deployment_resolves_to_the_platform() -> None:
    """That deployment holds credentials the SDK finds for itself, not a key here."""
    access = resolve_model_access(env={ENTERPRISE_VARIABLE: "true"})

    assert access == EnterprisePlatform(project=None, location=None)


def test_the_enterprise_platform_is_chosen_over_a_key_that_is_also_set() -> None:
    access = resolve_model_access(
        env={ENTERPRISE_VARIABLE: "true", API_KEY_VARIABLE: "model-key"}
    )

    assert access == EnterprisePlatform(project=None, location=None)


def test_the_enterprise_variable_is_spelled_as_the_sdk_reads_it() -> None:
    """The literal name the SDK reads, deliberately not the constant.

    A rename here that ``google-genai`` did not make would silently reach the
    developer platform for a deployment that authenticates perfectly well.
    """
    access = resolve_model_access(env={"GOOGLE_GENAI_USE_ENTERPRISE": "true"})

    assert isinstance(access, EnterprisePlatform)


def test_the_flag_is_read_as_the_sdk_reads_it() -> None:
    """``1`` selects the platform for the SDK, so it selects it here too."""
    assert isinstance(
        resolve_model_access(env={ENTERPRISE_VARIABLE: "1"}), EnterprisePlatform
    )


def test_an_enterprise_deployment_carries_the_project_and_location_it_names() -> None:
    access = resolve_model_access(
        env={
            ENTERPRISE_VARIABLE: "true",
            PROJECT_VARIABLE: "triage-prod",
            LOCATION_VARIABLE: "europe-west4",
        }
    )

    assert access == EnterprisePlatform(project="triage-prod", location="europe-west4")


def test_a_project_the_environment_does_not_name_is_left_for_discovery() -> None:
    """The platform derives it from the credentials it already holds."""
    access = resolve_model_access(
        env={ENTERPRISE_VARIABLE: "true", LOCATION_VARIABLE: "europe-west4"}
    )

    assert access == EnterprisePlatform(project=None, location="europe-west4")


def test_a_blank_project_is_treated_as_unnamed() -> None:
    """An exported-but-empty name would otherwise be sent as a real project."""
    access = resolve_model_access(
        env={ENTERPRISE_VARIABLE: "true", PROJECT_VARIABLE: ""}
    )

    assert access == EnterprisePlatform(project=None, location=None)


def test_a_project_named_without_the_platform_is_not_carried() -> None:
    """The SDK rejects a project outside the enterprise platform; never send one."""
    access = resolve_model_access(
        env={API_KEY_VARIABLE: "model-key", PROJECT_VARIABLE: "triage-prod"}
    )

    assert access == ApiKey("model-key")


def test_a_deployment_configuring_neither_way_is_refused() -> None:
    with pytest.raises(ConfigError, match=API_KEY_VARIABLE):
        resolve_model_access(env={})


def test_the_refusal_names_both_ways_of_configuring_it() -> None:
    """An operator on the enterprise platform is not told to go and find a key."""
    with pytest.raises(ConfigError, match=ENTERPRISE_VARIABLE):
        resolve_model_access(env={})


def test_an_empty_key_is_treated_as_absent() -> None:
    """An exported-but-blank name would otherwise fail on the first investigation."""
    with pytest.raises(ConfigError, match=API_KEY_VARIABLE):
        resolve_model_access(env={API_KEY_VARIABLE: ""})


def test_the_platform_switched_off_still_requires_a_key() -> None:
    with pytest.raises(ConfigError, match=API_KEY_VARIABLE):
        resolve_model_access(env={ENTERPRISE_VARIABLE: "false"})


def test_a_key_is_passed_to_the_client_as_a_key() -> None:
    assert client_arguments(ApiKey("model-key")) == {"api_key": "model-key"}


def test_the_platform_is_passed_to_the_client_as_the_platform() -> None:
    access = EnterprisePlatform(project="triage-prod", location="europe-west4")

    assert client_arguments(access) == {
        "enterprise": True,
        "project": "triage-prod",
        "location": "europe-west4",
    }


def test_a_project_nobody_named_is_left_out_of_the_client_entirely() -> None:
    """Sent as None it would override the discovery meant to answer for it."""
    assert client_arguments(EnterprisePlatform(project=None, location=None)) == {
        "enterprise": True
    }


def test_a_key_is_never_sent_alongside_the_platform() -> None:
    """The SDK rejects the pair, and would do so on the first investigation."""
    arguments = client_arguments(EnterprisePlatform(project="p", location="l"))

    assert "api_key" not in arguments
