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


def test_investigation_model_resolves_from_default_file_and_environment(
    tmp_path: Path,
) -> None:
    default = load_config(_write(tmp_path, SCOPED), env={})
    from_file = load_config(
        _write(tmp_path, SCOPED + "\ninvestigation:\n  model: some-other-model\n"),
        env={},
    )
    from_environment = load_config(
        _write(tmp_path, SCOPED + "\ninvestigation:\n  model: from-the-file\n"),
        env={"INVESTIGATION_MODEL": "from-the-environment"},
    )

    assert default.investigation.model == Investigation.DEFAULT_MODEL
    assert from_file.investigation.model == "some-other-model"
    assert from_environment.investigation.model == "from-the-environment"


def test_investigation_attempts_resolve_from_default_file_and_environment(
    tmp_path: Path,
) -> None:
    default = load_config(_write(tmp_path, SCOPED), env={})
    from_file = load_config(
        _write(tmp_path, SCOPED + "\ninvestigation:\n  max_attempts: 2\n"),
        env={},
    )
    from_environment = load_config(
        _write(tmp_path, SCOPED), env={"INVESTIGATION_MAX_ATTEMPTS": "1"}
    )

    assert default.investigation.max_attempts == 3
    assert from_file.investigation.max_attempts == 2
    assert from_environment.investigation.max_attempts == 1


def test_an_attempt_bound_below_one_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\ninvestigation:\n  max_attempts: 0\n")

    with pytest.raises(ValueError, match="max_attempts"):
        load_config(path, env={})


def test_a_credential_under_investigation_is_refused_by_name(tmp_path: Path) -> None:
    path = _write(tmp_path, SCOPED + "\ninvestigation:\n  api_key: sk-secret\n")

    with pytest.raises(ConfigError, match="api_key"):
        load_config(path, env={})


def test_the_attempt_bound_and_circuit_breakers_resolve_apart(
    tmp_path: Path,
) -> None:
    breakers_changed = load_config(
        _write(tmp_path, SCOPED + "\ncircuit_breakers:\n  max_agent_hops: 9\n"),
        env={},
    )
    attempts_changed = load_config(
        _write(tmp_path, SCOPED + "\ninvestigation:\n  max_attempts: 1\n"),
        env={},
    )

    assert breakers_changed.investigation.max_attempts == 3
    assert breakers_changed.circuit_breakers.max_agent_hops == 9
    assert attempts_changed.circuit_breakers.max_agent_hops == 8


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
