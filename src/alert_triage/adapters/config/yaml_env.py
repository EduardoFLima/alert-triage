"""Configuration resolved from an optional YAML file and the environment.

Every value is resolved once, at construction: the environment wins over the
file, the file wins over the built-in default, and a run that cannot resolve
``scope`` fails here rather than halfway through a triage.

The environment variable for a value is derived mechanically from its path in
the YAML — ``scope.datadog_team`` is ``SCOPE_DATADOG_TEAM`` — so a config key
added later needs no override wiring of its own.
"""

from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import Any

import yaml

from alert_triage.domain.config import CircuitBreakers, GroupingSettings, Scope
from alert_triage.ports.config import ConfigurationError

DEFAULT_CONFIG_PATH = Path("config.yaml")

_ConfigPath = tuple[str, ...]


class YamlEnvConfig:
    """The `Config` port backed by ``config.yaml`` plus environment overrides."""

    def __init__(
        self,
        *,
        config_path: Path = DEFAULT_CONFIG_PATH,
        environ: Mapping[str, str],
    ) -> None:
        """Resolve the whole configuration up front.

        Args:
            config_path: Where the YAML file would be. It is allowed not to
                exist — a deployment can configure everything through the
                environment instead.
            environ: The environment to read overrides from.

        Raises:
            ConfigurationError: If the file cannot be read as a config
                document, or if a mandatory value cannot be resolved from
                either source.
        """
        document = _read_yaml(config_path)
        self._scope = Scope(
            datadog_team=_required_text(document, environ, ("scope", "datadog_team"))
        )
        self._circuit_breakers = _settings(
            document, environ, "circuit_breakers", CircuitBreakers
        )
        self._grouping = _settings(document, environ, "grouping", GroupingSettings)
        self._critical_services = _critical_services(document, environ)

    @property
    def scope(self) -> Scope:
        """The team whose alerts this run triages."""
        return self._scope

    @property
    def circuit_breakers(self) -> CircuitBreakers:
        """Thresholds bounding an investigation."""
        return self._circuit_breakers

    @property
    def grouping(self) -> GroupingSettings:
        """How alerts are combined into incidents."""
        return self._grouping

    @property
    def critical_services(self) -> Mapping[str, Mapping[str, object]]:
        """Per-service overrides exactly as supplied, with nothing filled in."""
        return self._critical_services


def _read_yaml(config_path: Path) -> Mapping[str, Any]:
    """Parse the config file, treating its absence as an empty document."""
    if not config_path.exists():
        return {}
    try:
        document = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as error:
        raise ConfigurationError(f"{config_path} is not valid YAML: {error}") from error
    if document is None:
        return {}
    if not isinstance(document, dict):
        raise ConfigurationError(f"{config_path} must contain a mapping of sections")
    return document


def _env_name(path: _ConfigPath) -> str:
    """Map a config path to its environment variable name."""
    return "_".join(part.upper() for part in path)


def _at(document: Mapping[str, Any], path: _ConfigPath) -> Any:
    """Return the value at ``path``, or None where the path does not exist."""
    value: Any = document
    for part in path:
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _resolved(
    document: Mapping[str, Any], environ: Mapping[str, str], path: _ConfigPath
) -> Any:
    """Resolve one value, environment first, then the file."""
    override = environ.get(_env_name(path))
    return override if override is not None else _at(document, path)


def _required_text(
    document: Mapping[str, Any], environ: Mapping[str, str], path: _ConfigPath
) -> str:
    """Resolve a value the application refuses to start without."""
    value = _resolved(document, environ, path)
    if value is None:
        raise ConfigurationError(
            f"{'.'.join(path)} is required: set it in the config file or as "
            f"{_env_name(path)}. There is no default."
        )
    return str(value)


def _settings[Settings: (CircuitBreakers, GroupingSettings)](
    document: Mapping[str, Any],
    environ: Mapping[str, str],
    section: str,
    defaults: type[Settings],
) -> Settings:
    """Build a section that has built-in defaults from what was supplied.

    Only keys an operator actually set are passed along, so every key left
    alone keeps the documented default rather than being resolved to one.
    """
    overrides: dict[str, int] = {}
    for setting in fields(defaults):
        value = _resolved(document, environ, (section, setting.name))
        if value is not None:
            overrides[setting.name] = _as_int(value, (section, setting.name))
    return defaults(**overrides)


def _as_int(value: Any, path: _ConfigPath) -> int:
    """Coerce a resolved value to the integer the setting is declared as."""
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            f"{'.'.join(path)} must be a whole number, got {value!r}. "
            f"Check the config file and {_env_name(path)}."
        ) from error


def _critical_services(
    document: Mapping[str, Any], environ: Mapping[str, str]
) -> dict[str, dict[str, object]]:
    """Read the per-service overrides, substituting nothing of our own.

    A key absent here means "no override", which is a different thing from a
    key whose value happens to equal a default — so nothing is filled in,
    only what an operator wrote is carried through.
    """
    section = _at(document, ("critical_services",))
    if section is None:
        return {}
    if not isinstance(section, Mapping):
        raise ConfigurationError("critical_services must map service names to settings")
    return {
        str(service): _service_overrides(overrides, environ, str(service))
        for service, overrides in section.items()
    }


def _service_overrides(
    overrides: Any, environ: Mapping[str, str], service: str
) -> dict[str, object]:
    """Apply environment overrides to one service's supplied keys."""
    if not isinstance(overrides, Mapping):
        raise ConfigurationError(
            f"critical_services.{service} must be a mapping of settings"
        )
    return {
        str(key): environ.get(
            _env_name(("critical_services", service, str(key))), value
        )
        for key, value in overrides.items()
    }
