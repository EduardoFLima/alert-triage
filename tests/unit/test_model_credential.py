import pytest

from alert_triage.adapters.adk.credentials import (
    ALTERNATE_API_KEY_VARIABLE,
    API_KEY_VARIABLE,
    ENTERPRISE_VARIABLE,
    require_model_credential,
)
from alert_triage.ports.config import ConfigError


def test_the_api_key_resolves_from_the_environment() -> None:
    require_model_credential(env={API_KEY_VARIABLE: "model-key"})


def test_the_sdks_own_alternate_variable_is_accepted() -> None:
    """An operator who already exports GEMINI_API_KEY exports nothing new."""
    require_model_credential(env={ALTERNATE_API_KEY_VARIABLE: "model-key"})


def test_a_missing_credential_is_reported_as_required() -> None:
    with pytest.raises(ConfigError, match=API_KEY_VARIABLE):
        require_model_credential(env={})


def test_an_empty_credential_is_treated_as_absent() -> None:
    """An exported-but-blank name would otherwise fail on the first investigation."""
    with pytest.raises(ConfigError, match=API_KEY_VARIABLE):
        require_model_credential(env={API_KEY_VARIABLE: ""})


def test_the_enterprise_platform_authenticates_without_an_api_key() -> None:
    """That deployment holds credentials the SDK finds for itself, not a key here."""
    require_model_credential(env={ENTERPRISE_VARIABLE: "true"})


def test_the_enterprise_variable_is_spelled_as_the_sdk_reads_it() -> None:
    """The literal name the SDK reads, deliberately not the constant.

    A rename here that ``google-genai`` did not make would silently refuse a
    deployment that authenticates perfectly well.
    """
    require_model_credential(env={"GOOGLE_GENAI_USE_ENTERPRISE": "true"})


def test_the_enterprise_platform_switched_off_still_requires_a_key() -> None:
    with pytest.raises(ConfigError, match=API_KEY_VARIABLE):
        require_model_credential(env={ENTERPRISE_VARIABLE: "false"})


def test_the_environment_is_read_from_the_process_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_KEY_VARIABLE, raising=False)
    monkeypatch.delenv(ALTERNATE_API_KEY_VARIABLE, raising=False)
    monkeypatch.delenv(ENTERPRISE_VARIABLE, raising=False)

    with pytest.raises(ConfigError, match=API_KEY_VARIABLE):
        require_model_credential()
