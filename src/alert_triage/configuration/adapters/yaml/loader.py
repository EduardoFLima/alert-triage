"""Resolving configuration from an optional YAML file and the environment.

Resolution happens once, at startup, into an immutable value: a run does not
re-read the file or the environment halfway through, and a missing mandatory
value fails here rather than at first use.

The environment variable for a value is derived from its path in the file --
``scope.owner`` is ``SCOPE_OWNER`` -- so a new setting needs no override
wiring of its own. A watched service's own keys follow the same rule under its
name (``SCOPE_SERVICES_CHECKOUT_CRITICAL``).

Which services are watched is the one set the environment may state outright:
``SCOPE_SERVICES`` names them, replacing the file's list rather than adding to
it, because narrowing scope is what differs between deployments of the same
behavior and a container has no file of its own to edit. A service it names
that the file does not describe is watched with no settings beyond its name.
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, get_args, get_type_hints

import yaml

from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import (
    CircuitBreakers,
    Grouping,
    Ingestion,
    Investigation,
    Ledger,
    ReNotify,
    Scope,
    ScopedService,
    SpecialistModel,
)

DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass(frozen=True)
class ResolvedConfig:
    """Configuration resolved from file, environment, and defaults."""

    scope: Scope
    grouping: Grouping
    ingestion: Ingestion
    re_notify: ReNotify
    ledger: Ledger
    investigation: Investigation
    circuit_breakers: CircuitBreakers


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
        re_notify=_section(ReNotify, ("re_notify",), document, environment),
        ledger=_section(Ledger, ("ledger",), document, environment),
        investigation=_investigation(document, environment),
        circuit_breakers=_section(
            CircuitBreakers, ("circuit_breakers",), document, environment
        ),
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


_SERVICES = "services"
_NAME = "name"


def _scope(data: Mapping[str, Any], env: Mapping[str, str]) -> Scope:
    """Resolve the one section that has no default and no fallback.

    Either half names a scope: an owner watches everything it owns, services
    watch themselves whoever owns them, and both compose. What has no default
    is the section as a whole — a run may not decide for itself to watch
    everything.
    """
    supplied = _supplied(Scope, ("scope",), data, env, except_for=(_SERVICES,))
    services = _services(data.get(_SERVICES), env)
    if not supplied.get("owner") and not services:
        raise ConfigError(
            "scope is required and has no default: name an owner "
            "(scope.owner, or the SCOPE_OWNER environment variable), the "
            "services to watch (scope.services, or SCOPE_SERVICES), or both"
        )
    return Scope(**supplied, services=services)


def _services(entries: Any, env: Mapping[str, str]) -> tuple[ScopedService, ...]:
    """Read the services the scope watches. Naming none watches every one of them."""
    declared = _declared_services(entries, env)
    named = env.get(_env_name(("scope", _SERVICES)))
    if named is None:
        return declared
    described = {service.name: service for service in declared}
    return tuple(
        described.get(name, ScopedService(name=name)) for name in _names(named)
    )


def _names(named: str) -> tuple[str, ...]:
    """Read the comma-separated services an environment names. None is every one."""
    return tuple(name.strip() for name in named.split(",") if name.strip())


def _declared_services(
    entries: Any, env: Mapping[str, str]
) -> tuple[ScopedService, ...]:
    """Read the services the file describes, in the order it describes them."""
    if entries is None:
        return ()
    if not isinstance(entries, list):
        raise ConfigError(
            "Config section 'scope.services' must be a list of service entries"
        )
    return tuple(
        _service(position, entry, env) for position, entry in enumerate(entries)
    )


def _service(position: int, entry: Any, env: Mapping[str, str]) -> ScopedService:
    """Read one watched service, which is only worth writing to name a service.

    A service's own name keys its overrides, as a specialist's does
    (``SCOPE_SERVICES_CHECKOUT_CRITICAL``), so an operator adjusts one service
    without restating the list. The name itself is the key rather than a value
    under it: there is nothing to key an override of a name by.
    """
    location = f"scope.{_SERVICES}[{position}]"
    data = _entry(location, entry)
    name = data.get(_NAME)
    if name is None:
        raise ConfigError(
            f"{location}.{_NAME} is required: an entry naming no service has "
            f"nothing for its settings to describe"
        )
    return _named_service(str(name), data, env)


def _named_service(
    name: str, data: Mapping[str, Any], env: Mapping[str, str]
) -> ScopedService:
    """Resolve one named service's settings from its entry and its overrides."""
    supplied = _supplied(
        ScopedService,
        ("scope", _SERVICES, name),
        data,
        env,
        except_for=(_NAME,),
    )
    return ScopedService(name=name, **supplied)


_SPECIALISTS = "specialists"


def _investigation(
    document: Mapping[str, Any], env: Mapping[str, str]
) -> Investigation:
    """Resolve the one section carrying both settings and a keyed sub-section."""
    data = _section_data(document, "investigation")
    return Investigation(
        **_supplied(
            Investigation, ("investigation",), data, env, except_for=(_SPECIALISTS,)
        ),
        specialists=_specialists(data.get(_SPECIALISTS), env),
    )


def _specialists(entries: Any, env: Mapping[str, str]) -> Mapping[str, SpecialistModel]:
    """Read the per-specialist overrides. An absent section overrides nothing.

    Which specialists exist is not this module's to know: a name nobody
    declared is refused where the crew is assembled, which is the only place
    that can tell.
    """
    if entries is None:
        return {}
    if not isinstance(entries, dict):
        raise ConfigError(
            "Config section 'investigation.specialists' must be a mapping of "
            "specialist names"
        )
    return {name: _specialist(name, entry, env) for name, entry in entries.items()}


def _specialist(name: str, entry: Any, env: Mapping[str, str]) -> SpecialistModel:
    """Read one specialist's override, which is only worth writing to name a model."""
    path = ("investigation", _SPECIALISTS, name)
    supplied = _supplied(SpecialistModel, path, _entry(".".join(path), entry), env)
    if "model" not in supplied:
        raise ConfigError(
            f"investigation.specialists.{name}.model is required: an entry that "
            f"names no model overrides nothing"
        )
    return SpecialistModel(**supplied)


def _entry(location: str, entry: Any) -> Mapping[str, Any]:
    """Read one keyed entry's settings, tolerating an entry with none."""
    if entry is None:
        return {}
    if not isinstance(entry, dict):
        raise ConfigError(f"{location} must be a mapping of setting keys")
    return entry


def _supplied(
    cls: type[Any],
    path: tuple[str, ...],
    data: Mapping[str, Any],
    env: Mapping[str, str],
    *,
    except_for: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Collect the values an operator supplied, environment first.

    Keys nobody supplied are left out entirely, so the dataclass applies its
    own documented default rather than this function guessing one.

    ``except_for`` names the keys of a section that are sections themselves,
    resolved by the caller that knows their shape: a mapping has no
    environment variable to read it from and no type to coerce it to.
    """
    hints = get_type_hints(cls)
    known = [field.name for field in fields(cls)]
    _reject_unknown(known, path, data)

    supplied: dict[str, Any] = {}
    for name in (one for one in known if one not in except_for):
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


TRUE = ("true", "yes", "1")
FALSE = ("false", "no", "0")


def _coerce(raw: str, target: Any, path: tuple[str, ...]) -> Any:
    """Read an environment variable as the type its config key is declared with."""
    target = _stated(target)
    if target is str:
        return raw
    if target is bool:
        return _as_bool(raw, path)
    try:
        return target(raw)
    except (TypeError, ValueError) as error:
        raise ConfigError(
            f"{_env_name(path)}={raw!r} is not a valid {target.__name__} "
            f"for config key '{'.'.join(path)}'"
        ) from error


def _stated(target: Any) -> Any:
    """The type an operator states, for a key that may also be left unstated.

    A variable that is present states a value, so ``X | None`` is coerced as
    ``X``: the way to leave the key unstated is not to set it.
    """
    alternatives = [
        alternative for alternative in get_args(target) if alternative is not type(None)
    ]
    if len(alternatives) == 1:
        return alternatives[0]
    return target


def _as_bool(raw: str, path: tuple[str, ...]) -> bool:
    """Read a flag, refusing anything that is neither true nor false.

    ``bool("false")`` is ``True``, so the built-in call every other type takes
    would read a stand-down as a declaration — which is the worst reading
    available for a flag like ``critical``.
    """
    stated = raw.strip().lower()
    if stated in TRUE:
        return True
    if stated in FALSE:
        return False
    raise ConfigError(
        f"{_env_name(path)}={raw!r} is neither true nor false for config key "
        f"'{'.'.join(path)}': use one of {', '.join((*TRUE, *FALSE))}"
    )
