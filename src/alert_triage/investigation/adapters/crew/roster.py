from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import replace
from typing import NoReturn

from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import SpecialistModel
from alert_triage.investigation.adapters.crew.specialists.apm import APM_SPECIALIST
from alert_triage.investigation.adapters.crew.specialists.infrastructure import (
    INFRASTRUCTURE_SPECIALIST,
)
from alert_triage.investigation.adapters.crew.specialists.logs import LOGS_SPECIALIST
from alert_triage.investigation.adapters.crew.specialists.trace import (
    TRACE_SPECIALIST,
)
from alert_triage.investigation.domain.specialist import Specialist

CREW: tuple[Specialist, ...] = (
    LOGS_SPECIALIST,
    APM_SPECIALIST,
    TRACE_SPECIALIST,
    INFRASTRUCTURE_SPECIALIST,
)


def offered_from(
    declared: "Sequence[Specialist]", providers: AbstractSet[str]
) -> tuple[Specialist, ...]:
    return tuple(
        specialist
        for specialist in declared
        if {toolset.provider for toolset in specialist.toolsets} <= providers
    )


def crew_for(
    configured: Mapping[str, SpecialistModel], providers: AbstractSet[str]
) -> tuple[Specialist, ...]:
    declared = {specialist.name for specialist in CREW}
    unknown = sorted(set(configured) - declared)
    if unknown:
        _raise_unknown_specialist_config_error(declared, unknown)

    crew = offered_from(CREW, providers)
    if not crew:
        _raise_missing_provider_config_error(providers)

    return tuple(
        replace(specialist, model=configured[specialist.name].model)
        if specialist.name in configured
        else specialist
        for specialist in crew
    )


def _raise_unknown_specialist_config_error(
    declared: AbstractSet[str], unknown: Sequence[str]
) -> NoReturn:
    raise ConfigError(
        f"Unknown specialist(s) under 'investigation.specialists': "
        f"{', '.join(unknown)}. Declared specialists: "
        f"{', '.join(sorted(declared))}"
    )


def _raise_missing_provider_config_error(providers: AbstractSet[str]) -> NoReturn:
    wanted = sorted(
        {toolset.provider for specialist in CREW for toolset in specialist.toolsets}
    )
    held = ", ".join(sorted(providers)) or "none"
    raise ConfigError(
        f"No specialist can be run: this deployment configured {held}, and "
        f"every declared specialist needs one of {', '.join(wanted)}. "
        f"Configure a provider's endpoint and credentials in the environment."
    )
