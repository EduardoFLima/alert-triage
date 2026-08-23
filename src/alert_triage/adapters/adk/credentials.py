"""How an investigation's model is reached and paid for, read from the environment.

Deliberately not part of the YAML-backed configuration, for the reason
``adapters/datadog/connection.py`` already gives: *which* model reasons is a
statement about how the system triages and belongs in ``config.yaml``, while
the credential that model costs to reach describes the account a deployment
spends against and changes when the same image runs somewhere else.

The variable names are the Google GenAI SDK's own rather than this project's
``section.key`` mapping, which is why they live in the adapter that owns that
SDK: an operator who already exports ``GOOGLE_API_KEY`` exports nothing new.

What is resolved here is *supplied* to the model rather than left for the SDK
to rediscover. The SDK reads the process environment; a run reads the process
environment supplemented by its ``.env``, and those are not the same picture of
the world. Resolving the access and handing it over is what makes them agree —
and it is what makes the refusal below trustworthy, because the value that
refusal is built from is the value the model is built from.

Nothing here imports the SDK: these are the names its client constructor takes,
which keeps the resolution testable without a model, a client, or a network.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from alert_triage.ports.config import ConfigError

API_KEY_VARIABLE = "GOOGLE_API_KEY"
ALTERNATE_API_KEY_VARIABLE = "GEMINI_API_KEY"
ENTERPRISE_VARIABLE = "GOOGLE_GENAI_USE_ENTERPRISE"
PROJECT_VARIABLE = "GOOGLE_CLOUD_PROJECT"
LOCATION_VARIABLE = "GOOGLE_CLOUD_LOCATION"
ENTERPRISE_ENABLED = frozenset({"true", "1"})


@dataclass(frozen=True)
class ApiKey:
    """A deployment that pays for its model with a key.

    Attributes:
        key: The key the model is reached with.
    """

    key: str


@dataclass(frozen=True)
class EnterprisePlatform:
    """A deployment that reasons against the enterprise platform.

    It authenticates with the credentials it already holds rather than with a
    key of its own, which is why there is none here.

    Attributes:
        project: The project investigations are billed to, or ``None`` to let
            the platform's own credential discovery name it.
        location: Where the requests are made, or ``None`` for the SDK's
            default.
    """

    project: str | None
    location: str | None


ModelAccess = ApiKey | EnterprisePlatform
"""How an investigation's model is reached: one shape or the other, never both.

The SDK rejects a project without the enterprise platform, and rejects a key
alongside platform credentials. Deciding here, once, is what keeps those
contradictions unrepresentable rather than deferred to the first investigation.
"""


def resolve_model_access(env: Mapping[str, str] | None = None) -> ModelAccess:
    """Resolve how an investigation reaches its model, or refuse to start.

    Args:
        env: Environment to read from. Defaults to the process's.

    Returns:
        How the model is reached, in the one shape that deployment implies.

    Raises:
        ConfigError: The model has no credential. A run that cannot reason
            would fetch alerts, group them, and fail on the first incident due
            an investigation — having spent the attempt that failure counts.
    """
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
    """State the access in the keywords the SDK's client constructor takes.

    Only the keywords that shape allows: the SDK raises on a project given
    outside the enterprise platform, and a project or location nobody named is
    left out entirely so the platform's own discovery still answers for it.

    Args:
        access: How the model is reached.

    Returns:
        The keyword arguments the model's client is built with.
    """
    if isinstance(access, ApiKey):
        return {"api_key": access.key}
    named = {"project": access.project, "location": access.location}
    return {"enterprise": True, **{k: v for k, v in named.items() if v is not None}}


def _api_key(env: Mapping[str, str]) -> str | None:
    """The key under either name the SDK accepts, or nothing if neither is set."""
    return env.get(API_KEY_VARIABLE) or env.get(ALTERNATE_API_KEY_VARIABLE)


def _uses_enterprise_platform(env: Mapping[str, str]) -> bool:
    """Whether the model is reached through the platform rather than a key.

    The values are read exactly as ``google-genai`` reads them, so this agrees
    with the client it configures rather than refusing a deployment that would
    have worked.
    """
    return (env.get(ENTERPRISE_VARIABLE) or "").lower() in ENTERPRISE_ENABLED
