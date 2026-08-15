"""Where mail goes and how to submit it.

Deliberately not part of the YAML-backed configuration, on the rule the
Datadog credentials and the ledger path already follow: a relay, a sender, and
a recipient list change when the same triage behavior runs for a different
team, while what the system watches and how it groups stay identical. A key
naming any of them written into ``config.yaml`` is inert.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from alert_triage.ports.config import ConfigError

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
    """The deployment facts needed to submit mail for one deployment.

    Attributes:
        host: Hostname of the submission server. Its presence is what
            activates the channel.
        port: Submission port.
        sender: Address every report is sent from.
        recipients: Addresses every report is sent to. Never empty.
        username: Account to authenticate as, or ``None`` for a relay that
            wants no authentication.
        password: Password for that account. Paired with the username: one
            without the other is a configuration error, not an unauthenticated
            send.
    """

    host: str
    port: int
    sender: str
    recipients: tuple[str, ...]
    username: str | None = None
    password: str | None = None

    @property
    def credentials(self) -> tuple[str, str] | None:
        """The pair to log in with, or ``None`` when the relay wants none."""
        if self.username is None or self.password is None:
            return None
        return self.username, self.password


def resolve_email_settings(
    env: Mapping[str, str] | None = None,
) -> EmailSettings | None:
    """Resolve the email channel from the environment, or find it inactive.

    The host is what activates the channel. Saying nothing at all leaves it
    off, which is a decision; saying some of it and not the rest is a mistake,
    and is refused rather than quietly ignored.

    Args:
        env: Environment to read from. Defaults to the process's.

    Returns:
        The channel's settings, or ``None`` when the environment configured no
        email channel at all.

    Raises:
        ConfigError: The channel is configured only in part, or a value cannot
            be read as what it has to be.
    """
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
    """Read a setting the channel cannot be activated without."""
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
    """Read one half of the credential pair, refusing a half that stands alone."""
    value = supplied.get(variable)
    if value is None and partner in supplied:
        raise ConfigError(
            f"The email channel is configured in part: {partner} is set without "
            f"{variable}. An incomplete credential is not an unauthenticated send."
        )
    return value


def _recipients(supplied: Mapping[str, str]) -> tuple[str, ...]:
    """Read the recipient list, which one variable carries comma-separated."""
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
    """Read the submission port, which unlike the rest has a documented default."""
    port = supplied.get(SMTP_PORT_VARIABLE)
    if port is None:
        return DEFAULT_SMTP_PORT
    try:
        return int(port)
    except ValueError as error:
        raise ConfigError(
            f"{SMTP_PORT_VARIABLE}={port!r} is not a port number"
        ) from error
