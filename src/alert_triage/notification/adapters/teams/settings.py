"""Where a triage report is posted in Teams.

One variable, and deliberately no config-file key for it. A webhook URL names
one deployment's destination *and* authorises posting to it — a file shared
between deployments must not be able to carry one, on the same rule that keeps
the Datadog credentials and the mail relay out of ``config.yaml``.
"""

import os
from collections.abc import Mapping

TEAMS_WEBHOOK_URL_VARIABLE = "ALERT_TRIAGE_TEAMS_WEBHOOK_URL"


def resolve_teams_webhook_url(env: Mapping[str, str] | None = None) -> str | None:
    """Resolve where to post in Teams, or find the channel inactive.

    The channel has exactly one setting, so there is no half-configured state
    to refuse: the URL is either there or it is not.

    Args:
        env: Environment to read from. Defaults to the process's.

    Returns:
        The webhook URL, or ``None`` when the environment configured no Teams
        channel.
    """
    environment = os.environ if env is None else env
    return environment.get(TEAMS_WEBHOOK_URL_VARIABLE) or None
