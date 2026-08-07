"""Resolving configuration from an optional YAML file and the environment.

Resolution happens once, at startup, into an immutable value: a run does not
re-read the file or the environment halfway through, and a missing mandatory
value fails here rather than at first use.

The environment variable for a value is derived from its path in the file --
``scope.owner`` is ``SCOPE_OWNER`` -- so a new setting needs no override
wiring of its own. A per-service entry under ``critical_services``
follows the same rule (``CRITICAL_SERVICES_CHECKOUT_TIER``), but the set of
critical services itself comes from the file: the environment can adjust a
service the file declares, not declare one.
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, get_type_hints

import yaml

from alert_triage.ports.config import (
    CircuitBreakers,
    ConfigError,
    CriticalService,
    Grouping,
    Ingestion,
    Scope,
)

DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass(frozen=True)
class ResolvedConfig:
    """Configuration resolved from file, environment, and defaults."""

    scope: Scope
    grouping: Grouping
    ingestion: Ingestion
    circuit_breakers: CircuitBreakers
    critical_services: Mapping[str, CriticalService]


def load_config(
    path: Path = DEFAULT_CONFIG_PATH, env: Mapping[str, str] | None = None
) -> ResolvedConfig:
    """Resolve configuration, or refuse to start.

    Args:
        path: Where the optional config file would be. Its absence is fine.
        env: Environment to read overrides from. Defaults to the process's.

    Returns:
        The resolved configuration.

    Raises:
        ConfigError: The file is unreadable or malformed, names a key that
            does not exist, or leaves the mandatory ``scope`` unresolved.
    """
    document = _read(path)
    environment = os.environ if env is None else env
    return ResolvedConfig(
        scope=_scope(_section_data(document, "scope"), environment),
        grouping=_section(Grouping, ("grouping",), document, environment),
        ingestion=_section(Ingestion, ("ingestion",), document, environment),
        circuit_breakers=_section(
            CircuitBreakers, ("circuit_breakers",), document, environment
        ),
        critical_services=_critical_services(document, environment),
    )


def _read(path: Path) -> Mapping[str, Any]:
    """Parse the config file, treating absent and empty alike as no settings."""
    if not path.is_file():
        return {}
    try:
        document = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not valid YAML: {error}") from error
    if document is None:
        return {}
    if not isinstance(document, dict):
        raise ConfigError(f"{path} must contain a mapping of config sections")
    return document


def _section_data(document: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """Read one section, tolerating both an absent and an empty section."""
    section = document.get(name)
    if section is None:
        return {}
    if not isinstance(section, dict):
        raise ConfigError(f"Config section '{name}' must be a mapping")
    return section


def _section[SectionT](
    cls: type[SectionT],
    path: tuple[str, ...],
    document: Mapping[str, Any],
    env: Mapping[str, str],
) -> SectionT:
    """Build a section from its file entries, its overrides, and its defaults."""
    return cls(**_supplied(cls, path, _section_data(document, path[-1]), env))


def _scope(data: Mapping[str, Any], env: Mapping[str, str]) -> Scope:
    """Resolve the one value that has no default and no fallback."""
    supplied = _supplied(Scope, ("scope",), data, env)
    if "owner" not in supplied:
        raise ConfigError(
            "scope.owner is required and has no default: set it in "
            "config.yaml or as the SCOPE_OWNER environment variable"
        )
    return Scope(**supplied)


def _critical_services(
    document: Mapping[str, Any], env: Mapping[str, str]
) -> Mapping[str, CriticalService]:
    """Read the declared critical services. An absent section declares none."""
    return {
        service: CriticalService(
            **_supplied(
                CriticalService,
                ("critical_services", service),
                _entry(service, entry),
                env,
            )
        )
        for service, entry in _section_data(document, "critical_services").items()
    }


def _entry(service: str, entry: Any) -> Mapping[str, Any]:
    """Read one critical service's thresholds; listing it with none is enough."""
    if entry is None:
        return {}
    if not isinstance(entry, dict):
        raise ConfigError(
            f"critical_services.{service} must be a mapping of threshold keys"
        )
    return entry


def _supplied(
    cls: type[Any],
    path: tuple[str, ...],
    data: Mapping[str, Any],
    env: Mapping[str, str],
) -> dict[str, Any]:
    """Collect the values an operator supplied, environment first.

    Keys nobody supplied are left out entirely, so the dataclass applies its
    own documented default rather than this function guessing one.
    """
    hints = get_type_hints(cls)
    known = [field.name for field in fields(cls)]
    _reject_unknown(known, path, data)

    supplied: dict[str, Any] = {}
    for name in known:
        override = env.get(_env_name((*path, name)))
        if override is not None:
            supplied[name] = _coerce(override, hints[name], (*path, name))
        elif name in data:
            supplied[name] = data[name]
    return supplied


def _reject_unknown(
    known: list[str], path: tuple[str, ...], data: Mapping[str, Any]
) -> None:
    """Fail on a key the schema has never heard of, rather than dropping it."""
    unknown = sorted(set(data) - set(known))
    if unknown:
        location = ".".join(path)
        raise ConfigError(
            f"Unknown config key(s) under '{location}': {', '.join(unknown)}. "
            f"Known keys: {', '.join(known)}"
        )


def _env_name(path: tuple[str, ...]) -> str:
    """Map a config path to its environment variable name, mechanically."""
    return "_".join(re.sub(r"[^0-9a-zA-Z]+", "_", part).upper() for part in path)


def _coerce(raw: str, target: type[Any], path: tuple[str, ...]) -> Any:
    """Read an environment variable as the type its config key is declared with."""
    if target is str:
        return raw
    try:
        return target(raw)
    except (TypeError, ValueError) as error:
        raise ConfigError(
            f"{_env_name(path)}={raw!r} is not a valid {target.__name__} "
            f"for config key '{'.'.join(path)}'"
        ) from error
