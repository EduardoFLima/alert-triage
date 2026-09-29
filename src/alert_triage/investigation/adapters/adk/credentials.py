"""Model credentials are deployment facts, resolved from the run environment."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from alert_triage.configuration.port import ConfigError

API_KEY_VARIABLE = "GOOGLE_API_KEY"
ALTERNATE_API_KEY_VARIABLE = "GEMINI_API_KEY"
ENTERPRISE_VARIABLE = "GOOGLE_GENAI_USE_ENTERPRISE"
PROJECT_VARIABLE = "GOOGLE_CLOUD_PROJECT"
LOCATION_VARIABLE = "GOOGLE_CLOUD_LOCATION"
ENTERPRISE_ENABLED = frozenset({"true", "1"})


@dataclass(frozen=True)
class ApiKey:
    key: str


@dataclass(frozen=True)
class EnterprisePlatform:
    project: str | None
    location: str | None


ModelAccess = ApiKey | EnterprisePlatform


def resolve_model_access(env: Mapping[str, str] | None = None) -> ModelAccess:
    environment = os.environ if env is None else env
    if _uses_enterprise_platform(environment):
        return EnterprisePlatform(
            project=environment.get(PROJECT_VARIABLE) or None,
            location=environment.get(LOCATION_VARIABLE) or None,
        )
    key = _api_key(environment)
    if not key:
        raise ConfigError(
            f"{API_KEY_VARIABLE} is required and has no default: set it (or "
            f"{ALTERNATE_API_KEY_VARIABLE}) in the environment, or set "
            f"{ENTERPRISE_VARIABLE} to authenticate against the enterprise "
            f"platform instead. Credentials are never read from config.yaml."
        )
    return ApiKey(key)


def client_arguments(access: ModelAccess) -> dict[str, Any]:
    """Only emit keys valid for the chosen auth shape; the SDK rejects mixes."""
    if isinstance(access, ApiKey):
        return {"api_key": access.key}
    named = {"project": access.project, "location": access.location}
    return {"enterprise": True, **{k: v for k, v in named.items() if v is not None}}


def _api_key(env: Mapping[str, str]) -> str | None:
    return env.get(API_KEY_VARIABLE) or env.get(ALTERNATE_API_KEY_VARIABLE)


def _uses_enterprise_platform(env: Mapping[str, str]) -> bool:
    """Accepted values match google-genai so resolution agrees with the client."""
    return (env.get(ENTERPRISE_VARIABLE) or "").lower() in ENTERPRISE_ENABLED
