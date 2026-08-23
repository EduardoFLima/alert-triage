"""The seam this change exists to close, exercised end to end.

The model's client reads the process environment; a run reads the process
environment supplemented by its ``.env``. These tests hold the two together:
whatever the run resolved is what the model is built to authenticate with,
whether the operator exported it or wrote it in a file.
"""

from pathlib import Path

from alert_triage.adapters.adk.credentials import resolve_model_access
from alert_triage.adapters.adk.model import build_model
from alert_triage.configuration.adapters.env_file import resolve_environment

A_MODEL = "gemini-2.5-flash"


def _written(tmp_path: Path, contents: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(contents)
    return path


def _model_built_from(path: Path, exported: dict[str, str]) -> dict[str, object]:
    """What the model would be built to authenticate with, given this world."""
    environment = resolve_environment(path, exported)
    return build_model(A_MODEL, resolve_model_access(environment)).client_kwargs or {}


def test_a_key_only_the_file_declares_reaches_the_model(tmp_path: Path) -> None:
    """The process exported nothing: without this, the model would find no key."""
    path = _written(tmp_path, "GOOGLE_API_KEY=from-the-file\n")

    assert _model_built_from(path, {}) == {"api_key": "from-the-file"}


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


def test_an_exported_key_wins_over_the_one_in_the_file(tmp_path: Path) -> None:
    """A container is never overridden by a file that happened to lie beside it."""
    path = _written(tmp_path, "GOOGLE_API_KEY=from-the-file\n")

    assert _model_built_from(path, {"GOOGLE_API_KEY": "from-the-process"}) == {
        "api_key": "from-the-process"
    }


def test_no_file_leaves_an_exported_deployment_exactly_as_it_was(
    tmp_path: Path,
) -> None:
    """The deployments that worked before this change go on working."""
    assert _model_built_from(tmp_path / ".env", {"GOOGLE_API_KEY": "exported"}) == {
        "api_key": "exported"
    }
