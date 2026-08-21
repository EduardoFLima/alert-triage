"""How an investigation's model is paid for, read from the environment.

Deliberately not part of the YAML-backed configuration, for the reason
``adapters/datadog/connection.py`` already gives: *which* model reasons is a
statement about how the system triages and belongs in ``config.yaml``, while
the key that model costs to reach describes the account a deployment spends
against and changes when the same image runs somewhere else.

The variable names are the Google GenAI SDK's own rather than this project's
``section.key`` mapping, which is why they live in the adapter that owns that
SDK: an operator who already exports ``GOOGLE_API_KEY`` exports nothing new.
Nothing is injected from here — the SDK reads the environment itself — so this
only answers whether an investigation could authenticate at all, early enough
that the answer costs no alerts.
"""

import os
from collections.abc import Mapping

from alert_triage.ports.config import ConfigError

API_KEY_VARIABLE = "GOOGLE_API_KEY"
ALTERNATE_API_KEY_VARIABLE = "GEMINI_API_KEY"
ENTERPRISE_VARIABLE = "GOOGLE_GENAI_USE_ENTERPRISE"

ENTERPRISE_ENABLED = frozenset({"true", "1"})


def require_model_credential(env: Mapping[str, str] | None = None) -> None:
    """Refuse to start unless an investigation could authenticate its model.

    Args:
        env: Environment to read from. Defaults to the process's.

    Raises:
        ConfigError: The model has no credential. A run that cannot reason
            would fetch alerts, group them, and fail on the first incident due
            an investigation — having spent the attempt that failure counts.
    """
    environment = os.environ if env is None else env
    if _uses_enterprise_platform(environment) or _api_key(environment):
        return
    raise ConfigError(
        f"{API_KEY_VARIABLE} is required and has no default: set it (or "
        f"{ALTERNATE_API_KEY_VARIABLE}) in the environment, or set "
        f"{ENTERPRISE_VARIABLE} to authenticate against the enterprise "
        f"platform instead. Credentials are never read from config.yaml."
    )


def _api_key(env: Mapping[str, str]) -> str | None:
    """The key under either name the SDK accepts, or nothing if neither is set."""
    return env.get(API_KEY_VARIABLE) or env.get(ALTERNATE_API_KEY_VARIABLE)


def _uses_enterprise_platform(env: Mapping[str, str]) -> bool:
    """Whether the SDK will authenticate against the platform rather than a key.

    Read exactly as ``google-genai`` reads it, so this agrees with the client
    it guards rather than refusing a deployment that would have worked.
    """
    return (env.get(ENTERPRISE_VARIABLE) or "").lower() in ENTERPRISE_ENABLED
