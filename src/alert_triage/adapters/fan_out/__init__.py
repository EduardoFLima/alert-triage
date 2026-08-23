"""Fan-out adapter: one ``Notifier`` that stands for every configured channel."""

from alert_triage.adapters.fan_out.notifier import FanOutNotifier

__all__ = ["FanOutNotifier"]
