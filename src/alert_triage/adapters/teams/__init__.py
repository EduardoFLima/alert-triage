"""Teams adapters: a ``Notifier`` implementation that posts to Microsoft Teams."""

from alert_triage.adapters.teams.http import (
    TIMEOUT_SECONDS,
    Post,
    post_over_urllib,
)
from alert_triage.adapters.teams.notifier import (
    ADAPTIVE_CARD_CONTENT_TYPE,
    CARD_SCHEMA,
    CARD_VERSION,
    TeamsNotifier,
    render,
)
from alert_triage.adapters.teams.settings import (
    TEAMS_WEBHOOK_URL_VARIABLE,
    resolve_teams_webhook_url,
)

__all__ = [
    "ADAPTIVE_CARD_CONTENT_TYPE",
    "CARD_SCHEMA",
    "CARD_VERSION",
    "TEAMS_WEBHOOK_URL_VARIABLE",
    "TIMEOUT_SECONDS",
    "Post",
    "TeamsNotifier",
    "post_over_urllib",
    "render",
    "resolve_teams_webhook_url",
]
