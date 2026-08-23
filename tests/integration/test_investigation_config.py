from pathlib import Path

import pytest

from alert_triage.configuration.adapters.yaml import load_config
from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import Investigation

SCOPED = """
scope:
  owner: sre
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(body)
    return path


def test_investigation_settings_default_when_the_section_is_absent(
    tmp_path: Path,
) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={})

    assert config.investigation.model == Investigation.DEFAULT_MODEL
    assert config.investigation.max_attempts == 3


def test_the_operator_chooses_the_model_in_the_file(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\ninvestigation:\n  model: some-other-model\n")

    config = load_config(path, env={})

    assert config.investigation.model == "some-other-model"


def test_the_environment_wins_over_the_file_for_investigation(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\ninvestigation:\n  model: from-the-file\n")

    config = load_config(path, env={"INVESTIGATION_MODEL": "from-the-environment"})

    assert config.investigation.model == "from-the-environment"


def test_the_attempt_bound_resolves_from_the_environment_alone(tmp_path: Path) -> None:
    config = load_config(
        _write(tmp_path, SCOPED), env={"INVESTIGATION_MAX_ATTEMPTS": "1"}
    )

    assert config.investigation.max_attempts == 1


def test_the_operator_bounds_the_attempts_in_the_file(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\ninvestigation:\n  max_attempts: 2\n")

    assert load_config(path, env={}).investigation.max_attempts == 2


def test_an_attempt_bound_below_one_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\ninvestigation:\n  max_attempts: 0\n")

    with pytest.raises(ValueError, match="max_attempts"):
        load_config(path, env={})


def test_a_credential_under_investigation_is_refused_by_name(tmp_path: Path) -> None:
    """Ignoring it would leave an operator believing a credential was supplied."""
    path = _write(tmp_path, SCOPED + "\ninvestigation:\n  api_key: sk-secret\n")

    with pytest.raises(ConfigError, match="api_key"):
        load_config(path, env={})


def test_the_attempt_bound_is_resolved_apart_from_the_circuit_breakers(
    tmp_path: Path,
) -> None:
    """One bounds a call inside an investigation; the other bounds investigations."""
    path = _write(tmp_path, SCOPED + "\ncircuit_breakers:\n  max_mcp_retries: 9\n")

    config = load_config(path, env={})

    assert config.investigation.max_attempts == 3
    assert config.circuit_breakers.max_mcp_retries == 9


def test_changing_the_attempt_bound_leaves_the_breakers_alone(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\ninvestigation:\n  max_attempts: 1\n")

    config = load_config(path, env={})

    assert config.circuit_breakers.max_mcp_retries == 3


def test_a_specialist_may_be_given_a_model_of_its_own(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
investigation:
  model: the-default
  specialists:
    logs_specialist:
      model: a-bigger-model
""",
    )

    config = load_config(path, env={})

    assert config.investigation.model == "the-default"
    assert config.investigation.specialists["logs_specialist"].model == "a-bigger-model"


def test_no_specialist_section_leaves_every_specialist_on_the_default(
    tmp_path: Path,
) -> None:
    config = load_config(_write(tmp_path, SCOPED), env={})

    assert config.investigation.specialists == {}


def test_an_unknown_key_under_a_specialist_is_refused_by_name(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
investigation:
  specialists:
    logs_specialist:
      modle: a-typo
""",
    )

    with pytest.raises(ConfigError, match="modle"):
        load_config(path, env={})


def test_a_specialist_entry_naming_no_model_says_nothing_and_is_refused(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        SCOPED + "\ninvestigation:\n  specialists:\n    logs_specialist: {}\n",
    )

    with pytest.raises(ConfigError, match="logs_specialist"):
        load_config(path, env={})


def test_a_specialists_model_resolves_from_the_environment(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        SCOPED
        + """
investigation:
  specialists:
    logs_specialist:
      model: from-the-file
""",
    )

    config = load_config(
        path,
        env={"INVESTIGATION_SPECIALISTS_LOGS_SPECIALIST_MODEL": "from-the-environment"},
    )

    assert (
        config.investigation.specialists["logs_specialist"].model
        == "from-the-environment"
    )
