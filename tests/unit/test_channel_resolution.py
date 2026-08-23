import pytest

from alert_triage.adapters.email import (
    EMAIL_FROM_VARIABLE,
    EMAIL_TO_VARIABLE,
    SMTP_HOST_VARIABLE,
    EmailNotifier,
)
from alert_triage.adapters.fan_out import FanOutNotifier
from alert_triage.adapters.teams import TEAMS_WEBHOOK_URL_VARIABLE, TeamsNotifier
from alert_triage.app.composition import resolve_notifier
from alert_triage.ports.config import ConfigError
from alert_triage.ports.notifier import Notifier

EMAIL_ENV = {
    SMTP_HOST_VARIABLE: "smtp.example.com",
    EMAIL_FROM_VARIABLE: "triage@example.com",
    EMAIL_TO_VARIABLE: "sre@example.com",
}
TEAMS_ENV = {
    TEAMS_WEBHOOK_URL_VARIABLE: (
        "https://prod-1.westeurope.logic.azure.com/workflows/abc/triggers/manual"
    )
}


def _channels(notifier: FanOutNotifier) -> list[type[Notifier]]:
    return [type(channel) for channel in notifier.channels]


def test_the_resolved_notifier_is_one_notifier_whatever_is_behind_it() -> None:
    notifier: Notifier = resolve_notifier(env=EMAIL_ENV)

    assert isinstance(notifier, Notifier)


def test_configuring_email_alone_activates_email_alone() -> None:
    assert _channels(resolve_notifier(env=EMAIL_ENV)) == [EmailNotifier]


def test_configuring_teams_alone_activates_teams_alone() -> None:
    assert _channels(resolve_notifier(env=TEAMS_ENV)) == [TeamsNotifier]


def test_the_absence_of_the_other_channel_is_not_an_error() -> None:
    resolve_notifier(env=TEAMS_ENV)


def test_configuring_both_channels_delivers_through_both() -> None:
    assert _channels(resolve_notifier(env=EMAIL_ENV | TEAMS_ENV)) == [
        EmailNotifier,
        TeamsNotifier,
    ]


def test_configuring_no_channel_at_all_refuses_to_start() -> None:
    with pytest.raises(ConfigError, match="at least one notification channel"):
        resolve_notifier(env={})


def test_the_refusal_is_a_configuration_error_like_a_missing_scope_or_credential() -> (
    None
):
    """Not a failure mode particular to notification: the same type, caught alike."""
    with pytest.raises(ConfigError):
        resolve_notifier(env={})


def test_a_half_configured_channel_still_refuses_rather_than_falling_back() -> None:
    """A working Teams channel does not excuse a broken email one."""
    half_configured = {
        variable: value
        for variable, value in EMAIL_ENV.items()
        if variable != EMAIL_TO_VARIABLE
    }

    with pytest.raises(ConfigError, match=EMAIL_TO_VARIABLE):
        resolve_notifier(env=TEAMS_ENV | half_configured)


def test_the_environment_is_read_from_the_process_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable, value in TEAMS_ENV.items():
        monkeypatch.setenv(variable, value)

    assert _channels(resolve_notifier()) == [TeamsNotifier]
