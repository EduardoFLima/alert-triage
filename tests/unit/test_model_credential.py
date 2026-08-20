import pytest

from alert_triage.adapters.adk.credentials import (
    ALTERNATE_API_KEY_VARIABLE,
    API_KEY_VARIABLE,
    VERTEX_AI_VARIABLE,
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


def test_vertex_ai_authenticates_without_an_api_key() -> None:
    """That deployment holds credentials the SDK finds for itself, not a key here."""
    require_model_credential(env={VERTEX_AI_VARIABLE: "true"})


def test_vertex_ai_switched_off_still_requires_a_key() -> None:
    with pytest.raises(ConfigError, match=API_KEY_VARIABLE):
        require_model_credential(env={VERTEX_AI_VARIABLE: "false"})


def test_the_environment_is_read_from_the_process_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_KEY_VARIABLE, raising=False)
    monkeypatch.delenv(ALTERNATE_API_KEY_VARIABLE, raising=False)
    monkeypatch.delenv(VERTEX_AI_VARIABLE, raising=False)

    with pytest.raises(ConfigError, match=API_KEY_VARIABLE):
        require_model_credential()
