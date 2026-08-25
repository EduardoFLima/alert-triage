"""What a specialist is, declared as data and nothing else.

A specialist is its name, the signal it reports under, what it is instructed to
look for, the shape of what it reports, the tools it may reach, and — where it
differs from its siblings — the model it reasons on. One value, declared in one
place. Adding a specialist is adding a declaration; widening what one may ask
is a word in a tuple.

Nothing here knows an agent framework. That is what lets a declaration outlive
the framework that currently runs it, and what makes a contributor's specialist
a file rather than an integration.
"""

from dataclasses import dataclass
from typing import Any

from alert_triage.investigation.contract import Signal


@dataclass(frozen=True)
class Toolset:
    """A group of tools on the platform, and which of them a specialist may reach.

    Both halves are needed and they bound different things: the platform is
    asked for the group, and the framework is told the names within it. Only
    the second is ours to enforce if the platform regroups its tools.

    Attributes:
        name: The toolset as the platform groups it.
        tools: The tools within it this specialist is permitted to call.
    """

    name: str
    tools: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject a toolset that reaches nothing, which is a silent specialist."""
        if not self.name.strip():
            raise ValueError("A toolset needs the name the platform groups it under")
        if not self.tools:
            raise ValueError(
                "A toolset naming no tools permits nothing: name what may be called"
            )


@dataclass(frozen=True)
class Specialist:
    """One specialist, declared whole.

    Attributes:
        name: What this specialist is called, in the agent and in configuration.
        signal: The observability dimension its findings are drawn from.
        instruction: What it is asked to look for, in the terms of the platform
            it queries. Platform-specific by necessity: a query dialect does
            not translate, and pretending otherwise is what this slice undid.
        output_schema: The shape it reports in. It has no free-text evidence
            field; it cites what it was shown.
        toolsets: What it may reach, and nothing else.
        model: The model it reasons on, or ``None`` to take the deployment's
            default.
    """

    name: str
    signal: Signal
    instruction: str
    output_schema: type[Any]
    toolsets: tuple[Toolset, ...]
    model: str | None = None

    def __post_init__(self) -> None:
        """Reject a declaration that could not run as one."""
        if not self.name.strip():
            raise ValueError(
                "A specialist needs a name to be configured and reported by"
            )
        if not isinstance(self.signal, Signal):
            raise ValueError(
                "A specialist needs the signal its findings are drawn from"
            )
        if not self.instruction.strip():
            raise ValueError(
                "A specialist needs an instruction: without one it looks for nothing"
            )
        if not self.toolsets:
            raise ValueError("A specialist with no toolsets can gather no evidence")
