"""Resolving configuration from an optional YAML file and the environment.

Resolution happens once, at startup, into an immutable value: a run does not
re-read the file or the environment halfway through, and a missing mandatory
value fails here rather than at first use.

The environment variable for a value is derived from its path in the file --
``scope.owner`` is ``SCOPE_OWNER`` -- so a new setting needs no override
wiring of its own. An entry of a keyed section follows the same rule
(``INVESTIGATION_SPECIALISTS_TRACE_SPECIALIST_MODEL``), and which entries
exist usually comes from the file: the environment adjusts one the file
declares rather than declaring one.

``scope.services`` is the exception, because a deployment with no file at all
has to be able to say what it watches: ``SCOPE_SERVICES`` holds the whole set
as comma-separated names and replaces the file's section outright. The
per-entry variables then adjust whichever set resulted.
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
    ServiceScope,
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


SECTIONS = (
    "scope",
    "grouping",
    "ingestion",
    "re_notify",
    "ledger",
    "investigation",
    "circuit_breakers",
)
"""Every section this file may hold, which is every section resolved below.

Named here rather than derived from ``ResolvedConfig`` so that a section
removed from the schema is refused by name rather than quietly ignored, and so
that a connection setting written into the behavior file is met with the same
answer.
"""


def _reject_unknown_sections(document: Mapping[str, Any]) -> None:
    """Fail on a section the schema has never heard of, rather than dropping it.

    A key that resolves nothing is almost always a key an operator believes is
    resolving something: a section that was renamed, a setting that moved to
    the environment, or a typo. Silence there is how a deployment runs for a
    week on a default it thought it had overridden.
    """
    unknown = sorted(set(document) - set(SECTIONS))
    if unknown:
        raise ConfigError(
            f"Unknown config section(s): {', '.join(unknown)}. "
            f"Known sections: {', '.join(SECTIONS)}"
        )


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


def _env_name(path: tuple[str, ...]) -> str:
    """Map a config path to its environment variable name, mechanically."""
    return "_".join(re.sub(r"[^0-9a-zA-Z]+", "_", part).upper() for part in path)


SERVICES_VARIABLE = _env_name(("scope", _SERVICES))
"""The one variable that declares a whole section rather than adjusting a key."""


def _scope(data: Mapping[str, Any], env: Mapping[str, str]) -> Scope:
    """Resolve the one section that has no default and no fallback.

    "At least one" is enforced here rather than in ``Scope`` itself so that a
    deployment configured with neither meets a ``ConfigError`` -- the failure
    the application already refuses to start on, carrying the message that says
    what to set.
    """
    supplied = _supplied(Scope, ("scope",), data, env, except_for=(_SERVICES,))
    services = _services(data.get(_SERVICES), env)
    if "owner" not in supplied and not services:
        raise ConfigError(
            "scope requires an owner, services, or both, and has no default: "
            "set scope.owner (SCOPE_OWNER) or scope.services (SCOPE_SERVICES) "
            "in config.yaml or the environment"
        )
    return Scope(**supplied, services=services)


def _services(entries: Any, env: Mapping[str, str]) -> Mapping[str, ServiceScope]:
    """Read the services in scope, which the environment may declare outright.

    ``SCOPE_SERVICES`` **replaces** the file's section rather than merging with
    it, so the resolved set is exactly the names it lists and a deployment with
    no file can still scope by service. A per-entry variable then adjusts
    whichever set resulted, which is what restores a criticality the replaced
    section had recorded.

    An empty mapping resolves to none in scope rather than to a filter matching
    nothing, so that writing the key and listing nothing under it can never
    reduce a run to watching nothing while still exiting cleanly.
    """
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
    """The service names one variable holds, separated by commas.

    Empty names are dropped rather than resolved as a service nothing is tagged
    with: a trailing comma is a typo, never a request to watch nothing.
    """
    return [name.strip() for name in declared.split(",") if name.strip()]


def _service(name: str, entry: Any, env: Mapping[str, str]) -> ServiceScope:
    """Read one service's entry, which is only worth writing to raise urgency."""
    path = ("scope", _SERVICES, name)
    return ServiceScope(
        **_supplied(ServiceScope, path, _entry(".".join(path), entry), env)
    )


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


def _coerce(raw: str, target: Any, path: tuple[str, ...]) -> Any:
    """Read an environment variable as the type its config key is declared with."""
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
    """Read a flag as the answer it is, rather than as a non-empty string.

    ``bool("false")`` is ``True``, which is how a deployment comes to run with
    the opposite of what it wrote. A word outside either set is refused rather
    than guessed at.
    """
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
    """The type a supplied value is read as, looking past an optional key.

    A key that may be left unset is declared ``T | None``, but a variable that
    was set is never the ``None`` half: what an operator wrote is read as ``T``,
    and leaving it unset is expressed by not setting it at all.
    """
    declared = [one for one in get_args(target) if one is not type(None)]
    if len(declared) == 1:
        return declared[0]  # type: ignore[no-any-return]
    return target  # type: ignore[no-any-return]
