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

from alert_triage.configuration.port import ConfigError
from alert_triage.configuration.settings import SpecialistModel
from alert_triage.investigation.adapters.datadog.specialists.apm import APM_SPECIALIST
from alert_triage.investigation.adapters.datadog.specialists.infrastructure import (
    INFRASTRUCTURE_SPECIALIST,
)
from alert_triage.investigation.adapters.datadog.specialists.logs import LOGS_SPECIALIST
from alert_triage.investigation.adapters.datadog.specialists.trace import (
    TRACE_SPECIALIST,
)
from alert_triage.investigation.domain.specialist import Specialist

CREW: tuple[Specialist, ...] = (
    LOGS_SPECIALIST,
    APM_SPECIALIST,
    TRACE_SPECIALIST,
    INFRASTRUCTURE_SPECIALIST,
)
"""Every specialist declared, and so every one the manager may consult.

A tuple rather than a sequence to walk: the order is the order they are offered
in, and which of them an incident needs is the manager's decision. Adding a
specialist widens what may be chosen and changes nothing else.

There is deliberately nothing here deriving the signals a report may claim.
That was right while every specialist ran on every investigation, and became a
lie the moment one could be skipped: what a report may claim is what the
investigation consulted, which only the investigation knows and now records.
"""


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
