"""The specialists an investigation runs, in the order it runs them.

A tuple, deliberately. The crew is data the coordinator walks, so adding a
specialist is adding an entry here and a declaration beside it — no coordinator
learns a tool name, and no caller learns how many specialists there are.

This is also the only place that can tell whether a configured specialist
exists, which is why a name nobody declared is refused here rather than by the
loader that read it.
"""

from collections.abc import Mapping
from dataclasses import replace

from alert_triage.adapters.adk.logs_agent import LOGS_SPECIALIST
from alert_triage.adapters.adk.specialists import Specialist
from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import SpecialistModel

CREW: tuple[Specialist, ...] = (LOGS_SPECIALIST,)
"""Every specialist declared. Slice 9 adds APM, traces, and infrastructure."""


def crew_for(configured: Mapping[str, SpecialistModel]) -> tuple[Specialist, ...]:
    """The crew to run, with the models an operator named applied to it.

    Args:
        configured: Per-specialist overrides, keyed by specialist name.

    Returns:
        The declarations to run, each carrying the model it reasons on where
        one was configured for it.

    Raises:
        ConfigError: A specialist was configured that nobody declared. Refused
            by name, like any key the schema has never heard of.
    """
    declared = {specialist.name for specialist in CREW}
    unknown = sorted(set(configured) - declared)
    if unknown:
        raise ConfigError(
            f"Unknown specialist(s) under 'investigation.specialists': "
            f"{', '.join(unknown)}. Declared specialists: "
            f"{', '.join(sorted(declared))}"
        )
    return tuple(
        replace(specialist, model=configured[specialist.name].model)
        if specialist.name in configured
        else specialist
        for specialist in CREW
    )
