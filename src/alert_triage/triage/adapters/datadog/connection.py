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

from alert_triage.configuration.port import ConfigError

DEFAULT_SITE = "datadoghq.com"

DEFAULT_WEB_SUBDOMAIN = "app"
"""Where the web app lives for an account that has not been given its own.

Datadog serves most accounts from ``app.<site>``, but an organisation may be
issued a sub-domain of its own — ``foobar.datadoghq.eu`` — and the pages it
serves are only reachable there. This is only ever the host a human is sent
to: the API and the MCP server have hosts of their own, which is why widening
this does not touch either.
"""

SITE_VARIABLE = "DD_SITE"
API_KEY_VARIABLE = "DD_API_KEY"
APP_KEY_VARIABLE = "DD_APP_KEY"
WEB_SUBDOMAIN_VARIABLE = "DD_WEB_SUBDOMAIN"


@dataclass(frozen=True)
class DatadogConnection:
    """The deployment facts needed to reach one Datadog account.

    Attributes:
        site: Datadog regional site, e.g. ``datadoghq.eu``.
        api_key: Datadog API key.
        app_key: Datadog application key, which the Events API also requires.
        web_subdomain: Where this account's web app is served from, which is
            ``app`` unless the organisation has a sub-domain of its own.
    """

    site: str
    api_key: str
    app_key: str
    web_subdomain: str = DEFAULT_WEB_SUBDOMAIN

    @property
    def web_host(self) -> str:
        """The host a link sends a human to, for this account.

        Derived rather than configured whole: the region is already resolved
        and an operator overriding a sub-domain should not have to restate the
        site beside it.
        """
        return f"{self.web_subdomain}.{self.site}"


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
        web_subdomain=environment.get(WEB_SUBDOMAIN_VARIABLE) or DEFAULT_WEB_SUBDOMAIN,
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
