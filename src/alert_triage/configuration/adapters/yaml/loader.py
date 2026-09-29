"""The environment adjusts settings by path; ``SCOPE_SERVICES`` declares a set."""

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
    ServiceScope,
    SpecialistModel,
)

DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass(frozen=True)
class ResolvedConfig:
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
    """Resolve configuration, or refuse to start."""
    document = _read(path)
    _reject_unknown_sections(document)
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
    """Treat absent and empty config files alike as no settings."""
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


SECTIONS = (
    "scope",
    "grouping",
    "ingestion",
    "re_notify",
    "ledger",
    "investigation",
    "circuit_breakers",
)
# Explicit so retired sections and credentials in the behavior file fail by name.


def _reject_unknown_sections(document: Mapping[str, Any]) -> None:
    """Unknown sections should fail before a deployment runs on a default."""
    unknown = sorted(set(document) - set(SECTIONS))
    if unknown:
        raise ConfigError(
            f"Unknown config section(s): {', '.join(unknown)}. "
            f"Known sections: {', '.join(SECTIONS)}"
        )


def _section_data(document: Mapping[str, Any], name: str) -> Mapping[str, Any]:
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
    return cls(**_supplied(cls, path, _section_data(document, path[-1]), env))


_OWNER = "owner"
_SERVICES = "services"
_ENV = "env"


def _env_name(path: tuple[str, ...]) -> str:
    return "_".join(re.sub(r"[^0-9a-zA-Z]+", "_", part).upper() for part in path)


OWNER_VARIABLE = _env_name(("scope", _OWNER))
ENV_VARIABLE = _env_name(("scope", _ENV))
SERVICES_VARIABLE = _env_name(("scope", _SERVICES))


def _scope(data: Mapping[str, Any], env: Mapping[str, str]) -> Scope:
    """Keep the mandatory scope check in the adapter so it raises ConfigError."""
    environment = _supplied(
        Scope, ("scope",), data, env, except_for=(_OWNER, _SERVICES)
    )
    _reject_blank_environment(environment)
    owner = _owner(data, env)
    services = _services(data.get(_SERVICES), env)
    if owner is None and not services:
        raise ConfigError(
            "scope requires an owner, services, or both, and has no default: "
            "set scope.owner (SCOPE_OWNER) or scope.services (SCOPE_SERVICES) "
            "in config.yaml or the environment"
        )
    return Scope(owner=owner, services=services, **environment)


def _reject_blank_environment(supplied: Mapping[str, Any]) -> None:
    """Blank would otherwise silently widen the run to every environment."""
    if _ENV in supplied and not str(supplied[_ENV]).strip():
        raise ConfigError(
            f"scope.env ({ENV_VARIABLE}) must name an environment; leave it "
            f"unset to watch {Scope.DEFAULT_ENV}"
        )


def _owner(data: Mapping[str, Any], env: Mapping[str, str]) -> str | None:
    owner: str | None = env.get(OWNER_VARIABLE, data.get(_OWNER))
    return owner


def _services(entries: Any, env: Mapping[str, str]) -> Mapping[str, ServiceScope]:
    """``SCOPE_SERVICES`` replaces the file's set rather than merging with it."""
    declared = env.get(SERVICES_VARIABLE)
    if declared is not None:
        return {name: _service(name, {}, env) for name in _named_in(declared)}
    if entries is None:
        return {}
    if not isinstance(entries, dict):
        raise ConfigError(
            "Config section 'scope.services' must be a mapping of service names"
        )
    return {name: _service(name, entry, env) for name, entry in entries.items()}


def _named_in(declared: str) -> list[str]:
    """Drop empty comma chunks rather than naming an untaggable service."""
    return [name.strip() for name in declared.split(",") if name.strip()]


def _service(name: str, entry: Any, env: Mapping[str, str]) -> ServiceScope:
    path = ("scope", _SERVICES, name)
    return ServiceScope(
        **_supplied(ServiceScope, path, _entry(".".join(path), entry), env)
    )


_SPECIALISTS = "specialists"


def _investigation(
    document: Mapping[str, Any], env: Mapping[str, str]
) -> Investigation:
    data = _section_data(document, "investigation")
    return Investigation(
        **_supplied(
            Investigation, ("investigation",), data, env, except_for=(_SPECIALISTS,)
        ),
        specialists=_specialists(data.get(_SPECIALISTS), env),
    )


def _specialists(entries: Any, env: Mapping[str, str]) -> Mapping[str, SpecialistModel]:
    """Specialist names are validated where the crew is assembled."""
    if entries is None:
        return {}
    if not isinstance(entries, dict):
        raise ConfigError(
            "Config section 'investigation.specialists' must be a mapping of "
            "specialist names"
        )
    return {name: _specialist(name, entry, env) for name, entry in entries.items()}


def _specialist(name: str, entry: Any, env: Mapping[str, str]) -> SpecialistModel:
    path = ("investigation", _SPECIALISTS, name)
    supplied = _supplied(SpecialistModel, path, _entry(".".join(path), entry), env)
    if "model" not in supplied:
        raise ConfigError(
            f"investigation.specialists.{name}.model is required: an entry that "
            f"names no model overrides nothing"
        )
    return SpecialistModel(**supplied)


def _entry(location: str, entry: Any) -> Mapping[str, Any]:
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
    """Leave absent keys out so dataclass defaults remain the source of truth."""
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
    """Unknown keys should fail before a deployment runs on a default."""
    unknown = sorted(set(data) - set(known))
    if unknown:
        location = ".".join(path)
        raise ConfigError(
            f"Unknown config key(s) under '{location}': {', '.join(unknown)}. "
            f"Known keys: {', '.join(known)}"
        )


def _coerce(raw: str, target: Any, path: tuple[str, ...]) -> Any:
    declared = _settable(target)
    if declared is str:
        return raw
    if declared is bool:
        return _as_yes_or_no(raw, path)
    try:
        return declared(raw)
    except (TypeError, ValueError) as error:
        raise ConfigError(
            f"{_env_name(path)}={raw!r} is not a valid {declared.__name__} "
            f"for config key '{'.'.join(path)}'"
        ) from error


_YES = frozenset({"1", "true", "yes", "on"})
_NO = frozenset({"0", "false", "no", "off"})


def _as_yes_or_no(raw: str, path: tuple[str, ...]) -> bool:
    """Avoid ``bool("false")`` turning an explicit no into yes."""
    named = raw.strip().lower()
    if named in _YES:
        return True
    if named in _NO:
        return False
    raise ConfigError(
        f"{_env_name(path)}={raw!r} is neither a yes nor a no for config key "
        f"'{'.'.join(path)}'. A yes is one of: {', '.join(sorted(_YES))}"
    )


def _settable(target: Any) -> type[Any]:
    """Read a set optional key as its concrete type, never as ``None``."""
    declared = [one for one in get_args(target) if one is not type(None)]
    if len(declared) == 1:
        return declared[0]  # type: ignore[no-any-return]
    return target  # type: ignore[no-any-return]
