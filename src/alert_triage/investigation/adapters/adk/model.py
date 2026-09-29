"""ADK builds clients lazily; this only attaches resolved credentials."""

from google.adk.models import Gemini

from alert_triage.investigation.adapters.adk.credentials import (
    ModelAccess,
    client_arguments,
)


def build_model(model: str, access: ModelAccess) -> Gemini:
    return Gemini(model=model, client_kwargs=client_arguments(access))
