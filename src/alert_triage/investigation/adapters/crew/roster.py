"""The specialists an investigation runs, in the order it runs them.

A tuple, deliberately. The crew is data the coordinator walks, so adding a
specialist is adding an entry here and a declaration beside it — no coordinator
learns a tool name, and no caller learns how many specialists there are.

This is also the only place that can tell whether a configured specialist
exists, which is why a name nobody declared is refused here rather than by the
loader that read it.
"""

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import replace

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
"""Every specialist declared, and so every one the manager may consult.

A tuple rather than a sequence to walk: the order is the order they are offered
in, and which of them an incident needs is the manager's decision. Adding a
specialist widens what may be chosen and changes nothing else.

There is deliberately nothing here deriving the signals a report may claim.
That was right while every specialist ran on every investigation, and became a
lie the moment one could be skipped: what a report may claim is what the
investigation consulted, which only the investigation knows and now records.
"""


def offered_from(
    declared: "Sequence[Specialist]", providers: AbstractSet[str]
) -> tuple[Specialist, ...]:
    """The declarations a deployment holding these providers can actually run.

    A specialist is kept only where every provider its toolsets name is one the
    deployment configured. Every, not any: a declaration reaching two providers
    was written to gather from both, and running it against half its evidence
    would report a partial answer in the shape of a whole one.

    This is also the answer to two providers serving one signal. A deployment
    holding credentials for one of them offers one specialist for that signal
    and never sees the other, so nothing is consulted twice — without an
    operator naming a crew anywhere.

    Args:
        declared: Every specialist there is.
        providers: The providers this deployment configured.

    Returns:
        Those of them this deployment can reach, in declaration order.
    """
    return tuple(
        specialist
        for specialist in declared
        if {toolset.provider for toolset in specialist.toolsets} <= providers
    )


def crew_for(
    configured: Mapping[str, SpecialistModel], providers: AbstractSet[str]
) -> tuple[Specialist, ...]:
    """The crew to run: what this deployment can reach, on the models it named.

    Two independent decisions, in order. Which specialists a deployment can
    reach is decided by the providers it configured; what each of them reasons
    on is decided by configuration. A specialist filtered out by the first is
    still refused by name in the second if an operator configured it, because
    a model named for a specialist this deployment cannot run is a mistake
    worth hearing about rather than a line that quietly does nothing.

    Args:
        configured: Per-specialist overrides, keyed by specialist name.
        providers: The providers this deployment configured.

    Returns:
        The declarations to run, each carrying the model it reasons on where
        one was configured for it.

    Raises:
        ConfigError: A specialist was configured that nobody declared, or this
            deployment configured no provider that any declaration names —
            which is a crew of nobody, and a run with nothing to investigate
            with.
    """
    declared = {specialist.name for specialist in CREW}
    unknown = sorted(set(configured) - declared)
    if unknown:
        raise ConfigError(
            f"Unknown specialist(s) under 'investigation.specialists': "
            f"{', '.join(unknown)}. Declared specialists: "
            f"{', '.join(sorted(declared))}"
        )

    crew = offered_from(CREW, providers)
    if not crew:
        wanted = sorted(
            {toolset.provider for specialist in CREW for toolset in specialist.toolsets}
        )
        held = ", ".join(sorted(providers)) or "none"
        raise ConfigError(
            f"No specialist can be run: this deployment configured {held}, and "
            f"every declared specialist needs one of {', '.join(wanted)}. "
            f"Configure a provider's endpoint and credentials in the environment."
        )

    return tuple(
        replace(specialist, model=configured[specialist.name].model)
        if specialist.name in configured
        else specialist
        for specialist in crew
    )
