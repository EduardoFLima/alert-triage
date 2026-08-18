import logging
from datetime import UTC, datetime

import pytest

from alert_triage.app import main as entrypoint
from alert_triage.app.run import RunFailure, RunOutcome, Stage
from alert_triage.ports.config import ConfigError


def _executes(outcome: RunOutcome) -> object:
    """A composition root that runs, remembering the instant it was given."""

    def execute(*, now: datetime, **_: object) -> RunOutcome:
        instants.append(now)
        return outcome

    instants: list[datetime] = []
    execute.instants = instants  # type: ignore[attr-defined]
    return execute


def test_a_run_with_no_failures_exits_with_a_zero_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        entrypoint, "execute", _executes(RunOutcome(groups=2, delivered=2))
    )

    assert entrypoint.main() == 0


def test_a_run_with_a_failure_exits_with_a_non_zero_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = RunOutcome(
        groups=2,
        delivered=1,
        failures=(RunFailure(Stage.DELIVER, "checkout", "the relay refused it"),),
    )
    monkeypatch.setattr(entrypoint, "execute", _executes(outcome))

    assert entrypoint.main() != 0


def test_unusable_configuration_is_reported_rather_than_raised(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A scheduler reads a status; an operator reads a line, not a traceback."""

    def refuse(**_: object) -> RunOutcome:
        raise ConfigError("scope.owner is required and has no default")

    monkeypatch.setattr(entrypoint, "execute", refuse)

    with caplog.at_level(logging.ERROR):
        status = entrypoint.main()

    assert status != 0
    assert "scope.owner" in caplog.text


def test_the_failures_a_run_could_not_avoid_name_their_stage_and_service(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    outcome = RunOutcome(
        groups=1,
        delivered=0,
        failures=(RunFailure(Stage.DELIVER, "checkout", "the relay refused it"),),
    )
    monkeypatch.setattr(entrypoint, "execute", _executes(outcome))

    with caplog.at_level(logging.ERROR):
        entrypoint.main()

    assert "delivering the report" in caplog.text
    assert "checkout" in caplog.text


def test_the_run_is_given_the_environment_the_env_file_contributed_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reading the .env file happens once, here, and nothing below knows of it."""
    environments: list[object] = []

    def execute(*, now: datetime, env: object = None, **_: object) -> RunOutcome:
        environments.append(env)
        return RunOutcome()

    monkeypatch.setattr(entrypoint, "execute", execute)
    monkeypatch.setattr(
        entrypoint, "resolve_environment", lambda: {"SCOPE_OWNER": "from-the-env-file"}
    )

    entrypoint.main()

    assert environments == [{"SCOPE_OWNER": "from-the-env-file"}]


def test_the_run_is_given_one_instant_and_it_is_timezone_aware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The domain compares instants; a naive one would be a bug two layers down."""
    execute = _executes(RunOutcome())
    monkeypatch.setattr(entrypoint, "execute", execute)

    entrypoint.main()

    (instant,) = execute.instants  # type: ignore[attr-defined]
    assert instant.tzinfo is not None
    assert instant.utcoffset() == datetime.now(UTC).utcoffset()
