import os
from collections.abc import Mapping

TEAMS_WEBHOOK_URL_VARIABLE = "ALERT_TRIAGE_TEAMS_WEBHOOK_URL"


def resolve_teams_webhook_url(env: Mapping[str, str] | None = None) -> str | None:
    environment = os.environ if env is None else env
    return environment.get(TEAMS_WEBHOOK_URL_VARIABLE) or None
