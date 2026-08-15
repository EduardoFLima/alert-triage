"""Email adapters: a ``Notifier`` implementation that delivers by mail."""

from alert_triage.adapters.email.notifier import EmailNotifier, render
from alert_triage.adapters.email.settings import (
    DEFAULT_SMTP_PORT,
    EMAIL_FROM_VARIABLE,
    EMAIL_TO_VARIABLE,
    SMTP_HOST_VARIABLE,
    SMTP_PASSWORD_VARIABLE,
    SMTP_PORT_VARIABLE,
    SMTP_USERNAME_VARIABLE,
    EmailSettings,
    resolve_email_settings,
)
from alert_triage.adapters.email.smtp import (
    TIMEOUT_SECONDS,
    SmtpClient,
    SmtpFactory,
    attempt_starttls,
    open_smtp,
)

__all__ = [
    "DEFAULT_SMTP_PORT",
    "EMAIL_FROM_VARIABLE",
    "EMAIL_TO_VARIABLE",
    "SMTP_HOST_VARIABLE",
    "SMTP_PASSWORD_VARIABLE",
    "SMTP_PORT_VARIABLE",
    "SMTP_USERNAME_VARIABLE",
    "TIMEOUT_SECONDS",
    "EmailNotifier",
    "EmailSettings",
    "SmtpClient",
    "SmtpFactory",
    "attempt_starttls",
    "open_smtp",
    "render",
    "resolve_email_settings",
]
