"""Building the model an investigation reasons with, from what the run resolved.

Separate from ``credentials`` so that resolving how a model is reached stays
free of the SDK — and separate from ``logs_agent`` because what a model costs
to reach is not the Logs specialist's concern. This is the one place the two
meet.

The client is not built here. ADK builds it on first use, and a run that finds
no alerts should not have gone looking for credentials on its way to finding
none.
"""

from google.adk.models import Gemini

from alert_triage.adapters.adk.credentials import ModelAccess, client_arguments


def build_model(model: str, access: ModelAccess) -> Gemini:
    """Build the model, told how to authenticate rather than left to find out.

    Args:
        model: The model an investigation reasons with, from ``config.yaml``.
        access: How that model is reached, as the run's environment resolved it.

    Returns:
        The model, carrying the credentials its client will be built with.
    """
    return Gemini(model=model, client_kwargs=client_arguments(access))
