"""YAML + environment adapter for the ``Config`` port.

The file is optional and the environment always wins over it; what leaves this
package is a resolved, immutable ``Config``.
"""

from alert_triage.configuration.adapters.yaml.loader import ResolvedConfig, load_config

__all__ = ["ResolvedConfig", "load_config"]
