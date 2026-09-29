import os
from collections.abc import Mapping
from dataclasses import dataclass

from alert_triage.configuration.port import ConfigError

SMTP_HOST_VARIABLE = "ALERT_TRIAGE_SMTP_HOST"
SMTP_PORT_VARIABLE = "ALERT_TRIAGE_SMTP_PORT"
SMTP_USERNAME_VARIABLE = "ALERT_TRIAGE_SMTP_USERNAME"
SMTP_PASSWORD_VARIABLE = "ALERT_TRIAGE_SMTP_PASSWORD"
EMAIL_FROM_VARIABLE = "ALERT_TRIAGE_EMAIL_FROM"
EMAIL_TO_VARIABLE = "ALERT_TRIAGE_EMAIL_TO"

# The submission port, which is where STARTTLS is expected.
DEFAULT_SMTP_PORT = 587

RECIPIENT_SEPARATOR = ","


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int
    sender: str
    recipients: tuple[str, ...]
    username: str | None = None
    password: str | None = None

    @property
    def credentials(self) -> tuple[str, str] | None:
        if self.username is None or self.password is None:
            return None
        return self.username, self.password


def resolve_email_settings(
    env: Mapping[str, str] | None = None,
) -> EmailSettings | None:
    environment = os.environ if env is None else env
    supplied = {
        variable: value
        for variable in _EMAIL_VARIABLES
        if (value := environment.get(variable))
    }
    if not supplied:
        return None

    return EmailSettings(
        host=_required(supplied, SMTP_HOST_VARIABLE),
        port=_port(supplied),
        sender=_required(supplied, EMAIL_FROM_VARIABLE),
        recipients=_recipients(supplied),
        username=_paired(supplied, SMTP_USERNAME_VARIABLE, SMTP_PASSWORD_VARIABLE),
        password=_paired(supplied, SMTP_PASSWORD_VARIABLE, SMTP_USERNAME_VARIABLE),
    )


_EMAIL_VARIABLES = (
    SMTP_HOST_VARIABLE,
    SMTP_PORT_VARIABLE,
    SMTP_USERNAME_VARIABLE,
    SMTP_PASSWORD_VARIABLE,
    EMAIL_FROM_VARIABLE,
    EMAIL_TO_VARIABLE,
)


def _required(supplied: Mapping[str, str], variable: str) -> str:
    value = supplied.get(variable)
    if value is None:
        raise ConfigError(
            f"The email channel is configured in part: {variable} is missing. "
            f"Set it in the environment, or unset the other "
            f"ALERT_TRIAGE_SMTP_/ALERT_TRIAGE_EMAIL_ variables to leave the "
            f"channel inactive. Channel settings are never read from config.yaml."
        )
    return value


def _paired(supplied: Mapping[str, str], variable: str, partner: str) -> str | None:
    value = supplied.get(variable)
    if value is None and partner in supplied:
        raise ConfigError(
            f"The email channel is configured in part: {partner} is set without "
            f"{variable}. An incomplete credential is not an unauthenticated send."
        )
    return value


def _recipients(supplied: Mapping[str, str]) -> tuple[str, ...]:
    listed = _required(supplied, EMAIL_TO_VARIABLE)
    recipients = tuple(
        address.strip()
        for address in listed.split(RECIPIENT_SEPARATOR)
        if address.strip()
    )
    if not recipients:
        raise ConfigError(
            f"{EMAIL_TO_VARIABLE} names no recipient: a report has to reach somebody."
        )
    return recipients


def _port(supplied: Mapping[str, str]) -> int:
    port = supplied.get(SMTP_PORT_VARIABLE)
    if port is None:
        return DEFAULT_SMTP_PORT
    try:
        return int(port)
    except ValueError as error:
        raise ConfigError(
            f"{SMTP_PORT_VARIABLE}={port!r} is not a port number"
        ) from error
