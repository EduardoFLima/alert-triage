import os
from collections.abc import Mapping
from dataclasses import dataclass

from alert_triage.configuration.port import ConfigError

DEFAULT_SITE = "datadoghq.com"

DEFAULT_WEB_SUBDOMAIN = "app"

SITE_VARIABLE = "DD_SITE"
API_KEY_VARIABLE = "DD_API_KEY"
APP_KEY_VARIABLE = "DD_APP_KEY"
WEB_SUBDOMAIN_VARIABLE = "DD_WEB_SUBDOMAIN"


@dataclass(frozen=True)
class DatadogConnection:
    site: str
    api_key: str
    app_key: str
    web_subdomain: str = DEFAULT_WEB_SUBDOMAIN

    @property
    def web_host(self) -> str:
        return f"{self.web_subdomain}.{self.site}"


def resolve_connection(env: Mapping[str, str] | None = None) -> DatadogConnection:
    environment = os.environ if env is None else env
    return DatadogConnection(
        site=environment.get(SITE_VARIABLE) or DEFAULT_SITE,
        api_key=_required(environment, API_KEY_VARIABLE),
        app_key=_required(environment, APP_KEY_VARIABLE),
        web_subdomain=environment.get(WEB_SUBDOMAIN_VARIABLE) or DEFAULT_WEB_SUBDOMAIN,
    )


def _required(env: Mapping[str, str], variable: str) -> str:
    value = env.get(variable)
    if not value:
        raise ConfigError(
            f"{variable} is required and has no default: set it in the "
            f"environment. Credentials are never read from config.yaml."
        )
    return value
