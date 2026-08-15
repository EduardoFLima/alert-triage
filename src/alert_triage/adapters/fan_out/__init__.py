"""Fan-out adapter: one ``Notifier`` that stands for every configured channel."""

from alert_triage.adapters.fan_out.notifier import FanOutNotifier
from alert_triage.adapters.fan_out.resolution import resolve_notifier

__all__ = ["FanOutNotifier", "resolve_notifier"]
