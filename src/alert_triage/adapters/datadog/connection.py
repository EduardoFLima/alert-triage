"""Where Datadog is and how to authenticate against it.

Deliberately not part of the YAML-backed configuration. ``config.yaml``
describes how the system behaves; a site and a pair of API keys describe which
account a deployment points that behavior at, and change when the same image
runs somewhere else. They are resolved from the environment only, so a config
file stays portable and never grows a key shaped like a credential.

The variable names are Datadog's own conventions rather than this project's
``section.key`` mapping, which is why they live in the Datadog adapter: an
operator who already exports ``DD_API_KEY`` for the CLI exports nothing new.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from alert_triage.ports.config import ConfigError

DEFAULT_SITE = "datadoghq.com"

SITE_VARIABLE = "DD_SITE"
API_KEY_VARIABLE = "DD_API_KEY"
APP_KEY_VARIABLE = "DD_APP_KEY"


@dataclass(frozen=True)
class DatadogConnection:
    """The deployment facts needed to reach one Datadog account.

    Attributes:
        site: Datadog regional site, e.g. ``datadoghq.eu``.
        api_key: Datadog API key.
        app_key: Datadog application key, which the Events API also requires.
    """

    site: str
    api_key: str
    app_key: str


def resolve_connection(env: Mapping[str, str] | None = None) -> DatadogConnection:
    """Resolve how to reach Datadog, or refuse to start.

    Args:
        env: Environment to read from. Defaults to the process's.

    Returns:
        The resolved connection settings.

    Raises:
        ConfigError: A required credential is absent. Reaching the platform
            unauthenticated would fail later and less clearly.
    """
    environment = os.environ if env is None else env
    return DatadogConnection(
        site=environment.get(SITE_VARIABLE) or DEFAULT_SITE,
        api_key=_required(environment, API_KEY_VARIABLE),
        app_key=_required(environment, APP_KEY_VARIABLE),
    )


def _required(env: Mapping[str, str], variable: str) -> str:
    """Read a credential that has no default and no config-file fallback."""
    value = env.get(variable)
    if not value:
        raise ConfigError(
            f"{variable} is required and has no default: set it in the "
            f"environment. Credentials are never read from config.yaml."
        )
    return value
