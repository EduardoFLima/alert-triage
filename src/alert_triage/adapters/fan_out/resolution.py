"""Assembling the notifier a deployment's environment asked for.

Which channels exist is a consequence of what the environment configured, so
this is where the individual ``resolve_*`` functions meet: each channel is
activated by its own settings being present, and the result is the single
``Notifier`` a caller injects.

It lives beside the adapters rather than in ``app/`` because there is no
composition root yet, and slice 5 should have one function to call. When the
composition root arrives, it calls this one function too — the rule about
which channels are active is not something a wiring layer should re-derive.
"""

import os
from collections.abc import Mapping

from alert_triage.adapters.email.notifier import EmailNotifier
from alert_triage.adapters.email.settings import resolve_email_settings
from alert_triage.adapters.fan_out.notifier import FanOutNotifier
from alert_triage.adapters.teams.notifier import TeamsNotifier
from alert_triage.adapters.teams.settings import resolve_teams_webhook_url
from alert_triage.ports.config import ConfigError
from alert_triage.ports.notifier import Notifier


def resolve_notifier(env: Mapping[str, str] | None = None) -> FanOutNotifier:
    """Assemble the notification channels the environment configured, or refuse.

    Args:
        env: Environment to read from. Defaults to the process's.

    Returns:
        A notifier delivering to every configured channel. A deployment with
        one channel gets a fan-out over one, so nothing downstream is shaped by
        how many a deployment happens to have.

    Raises:
        ConfigError: No channel is configured, or one of them is configured
            only in part. A run that can investigate but can tell nobody what
            it found has no reason to start, and finding that out here beats
            finding it out when the first report is due.
    """
    environment = os.environ if env is None else env
    channels = _configured_channels(environment)
    if not channels:
        raise ConfigError(
            "No notification channel is configured: set at least one "
            "notification channel in the environment. A run that can tell "
            "nobody what it found has no reason to start."
        )
    return FanOutNotifier(channels)


def _configured_channels(env: Mapping[str, str]) -> list[Notifier]:
    """Build a channel for each set of settings the environment supplied."""
    channels: list[Notifier] = []
    email = resolve_email_settings(env)
    if email is not None:
        channels.append(EmailNotifier(email))
    webhook_url = resolve_teams_webhook_url(env)
    if webhook_url is not None:
        channels.append(TeamsNotifier(webhook_url))
    return channels
