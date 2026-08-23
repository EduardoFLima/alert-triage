import inspect
from dataclasses import fields

import pytest

from alert_triage.adapters.email import (
    DEFAULT_SMTP_PORT,
    EMAIL_FROM_VARIABLE,
    EMAIL_TO_VARIABLE,
    SMTP_HOST_VARIABLE,
    SMTP_PASSWORD_VARIABLE,
    SMTP_PORT_VARIABLE,
    SMTP_USERNAME_VARIABLE,
    resolve_email_settings,
)
from alert_triage.configuration.adapters.yaml.loader import ResolvedConfig
from alert_triage.configuration.port import ConfigError

CONFIGURED = {
    SMTP_HOST_VARIABLE: "smtp.example.com",
    EMAIL_FROM_VARIABLE: "triage@example.com",
    EMAIL_TO_VARIABLE: "sre@example.com",
}


def test_the_settings_resolve_from_the_environment() -> None:
    settings = resolve_email_settings(env=CONFIGURED | {SMTP_PORT_VARIABLE: "2525"})

    assert settings is not None
    assert settings.host == "smtp.example.com"
    assert settings.port == 2525
    assert settings.sender == "triage@example.com"
    assert settings.recipients == ("sre@example.com",)


def test_the_port_falls_back_to_the_documented_submission_default() -> None:
    settings = resolve_email_settings(env=CONFIGURED)

    assert settings is not None
    assert settings.port == DEFAULT_SMTP_PORT == 587


def test_several_recipients_are_a_comma_separated_list() -> None:
    settings = resolve_email_settings(
        env=CONFIGURED | {EMAIL_TO_VARIABLE: "sre@example.com, oncall@example.com"}
    )

    assert settings is not None
    assert settings.recipients == ("sre@example.com", "oncall@example.com")


def test_credentials_are_carried_when_the_relay_wants_them() -> None:
    settings = resolve_email_settings(
        env=CONFIGURED
        | {SMTP_USERNAME_VARIABLE: "triage", SMTP_PASSWORD_VARIABLE: "s3cret"}
    )

    assert settings is not None
    assert settings.credentials == ("triage", "s3cret")


def test_an_unauthenticated_relay_resolves_without_credentials() -> None:
    settings = resolve_email_settings(env=CONFIGURED)

    assert settings is not None
    assert settings.credentials is None


def test_saying_nothing_about_the_channel_leaves_it_inactive() -> None:
    """An absent channel is a decision, and takes no part in delivery."""
    assert resolve_email_settings(env={}) is None


def test_a_host_with_no_sender_is_a_configuration_error_naming_it() -> None:
    env = {
        key: value for key, value in CONFIGURED.items() if key != EMAIL_FROM_VARIABLE
    }

    with pytest.raises(ConfigError, match=EMAIL_FROM_VARIABLE):
        resolve_email_settings(env=env)


def test_a_host_with_no_recipient_is_a_configuration_error_naming_it() -> None:
    env = {key: value for key, value in CONFIGURED.items() if key != EMAIL_TO_VARIABLE}

    with pytest.raises(ConfigError, match=EMAIL_TO_VARIABLE):
        resolve_email_settings(env=env)


def test_a_recipient_list_of_nothing_but_separators_is_a_configuration_error() -> None:
    """A channel that would email nobody is half-configured, not configured."""
    with pytest.raises(ConfigError, match=EMAIL_TO_VARIABLE):
        resolve_email_settings(env=CONFIGURED | {EMAIL_TO_VARIABLE: " , , "})


def test_a_sender_with_no_host_is_a_configuration_error_not_a_silent_absence() -> None:
    """Configuring half a channel is a mistake, not a decision to leave it off."""
    with pytest.raises(ConfigError, match=SMTP_HOST_VARIABLE):
        resolve_email_settings(env={EMAIL_FROM_VARIABLE: "triage@example.com"})


def test_a_password_with_no_username_is_a_configuration_error() -> None:
    """Not a silent fallback to an unauthenticated send."""
    with pytest.raises(ConfigError, match=SMTP_USERNAME_VARIABLE):
        resolve_email_settings(env=CONFIGURED | {SMTP_PASSWORD_VARIABLE: "s3cret"})


def test_a_username_with_no_password_is_a_configuration_error() -> None:
    with pytest.raises(ConfigError, match=SMTP_PASSWORD_VARIABLE):
        resolve_email_settings(env=CONFIGURED | {SMTP_USERNAME_VARIABLE: "triage"})


def test_a_port_that_is_not_a_number_is_a_configuration_error() -> None:
    with pytest.raises(ConfigError, match=SMTP_PORT_VARIABLE):
        resolve_email_settings(env=CONFIGURED | {SMTP_PORT_VARIABLE: "submission"})


def test_the_environment_is_read_from_the_process_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable, value in CONFIGURED.items():
        monkeypatch.setenv(variable, value)

    settings = resolve_email_settings()

    assert settings is not None
    assert settings.host == "smtp.example.com"


def test_the_settings_have_no_config_file_to_be_read_from() -> None:
    """The resolver takes an environment and nothing else: there is no file path."""
    assert list(inspect.signature(resolve_email_settings).parameters) == ["env"]


def test_a_channel_setting_written_into_the_config_file_has_nowhere_to_land() -> None:
    """No resolved config section names a relay, a sender, or a recipient."""
    sections = {field.name for field in fields(ResolvedConfig)}

    assert not sections & {"smtp", "email", "notification", "notifications"}
