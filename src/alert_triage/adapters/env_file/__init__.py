"""Adapter for the ``.env`` file an operator keeps beside a checkout.

Not an implementation of a port: it supplies the environment the other
adapters already resolve their deployment facts from, so nothing below the
composition root learns that a file was involved.
"""

from alert_triage.adapters.env_file.environment import (
    DEFAULT_ENV_FILE,
    resolve_environment,
)

__all__ = ["DEFAULT_ENV_FILE", "resolve_environment"]
