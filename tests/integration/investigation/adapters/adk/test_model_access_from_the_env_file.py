"""The seam this change exists to close, exercised end to end.

The model's client reads the process environment; a run reads the process
environment supplemented by its ``.env``. These tests hold the two together:
whatever the run resolved is what the model is built to authenticate with,
whether the operator exported it or wrote it in a file.
"""

from pathlib import Path

from alert_triage.configuration.adapters.env_file import resolve_environment
from alert_triage.investigation.adapters.adk.credentials import resolve_model_access
from alert_triage.investigation.adapters.adk.model import build_model

A_MODEL = "gemini-2.5-flash"


def _written(tmp_path: Path, contents: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(contents)
    return path


def _model_built_from(path: Path, exported: dict[str, str]) -> dict[str, object]:
    """What the model would be built to authenticate with, given this world."""
    environment = resolve_environment(path, exported)
    return build_model(A_MODEL, resolve_model_access(environment)).client_kwargs or {}


def test_api_key_access_resolves_from_the_env_file_or_process(
    tmp_path: Path,
) -> None:
    """A container wins, a laptop file supplements, and no file changes nothing."""
    cases: tuple[tuple[Path, dict[str, str], dict[str, object]], ...] = (
        (
            _written(tmp_path, "GOOGLE_API_KEY=from-the-file\n"),
            {},
            {"api_key": "from-the-file"},
        ),
        (
            _written(tmp_path, "GOOGLE_API_KEY=from-the-file\n"),
            {"GOOGLE_API_KEY": "from-the-process"},
            {"api_key": "from-the-process"},
        ),
        (
            tmp_path / "absent.env",
            {"GOOGLE_API_KEY": "exported"},
            {"api_key": "exported"},
        ),
    )

    for path, exported, expected in cases:
        assert _model_built_from(path, exported) == expected


def test_the_platform_selected_only_in_the_file_reaches_the_model(
    tmp_path: Path,
) -> None:
    """The variable that sent us here: unexported, it selected nothing at all."""
    path = _written(
        tmp_path,
        "GOOGLE_GENAI_USE_ENTERPRISE=true\n"
        "GOOGLE_CLOUD_PROJECT=triage-prod\n"
        "GOOGLE_CLOUD_LOCATION=europe-west4\n",
    )

    assert _model_built_from(path, {}) == {
        "enterprise": True,
        "project": "triage-prod",
        "location": "europe-west4",
    }


def test_an_enterprise_deployment_is_never_given_a_key(tmp_path: Path) -> None:
    """It authenticates with credentials it already holds; the SDK rejects both."""
    path = _written(
        tmp_path, "GOOGLE_GENAI_USE_ENTERPRISE=true\nGOOGLE_API_KEY=a-key\n"
    )

    assert "api_key" not in _model_built_from(path, {})
