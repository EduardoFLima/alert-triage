"""What a specialist is, declared as data and nothing else.

A specialist is its name, the signal it reports under, what it is instructed to
look for, the shape of what it reports, the tools it may reach and whose server
serves each group of them, and — where it differs from its siblings — the model
it reasons on. One value, declared in one place. Adding a specialist is adding a
declaration; widening what one may ask is a word in a tuple; reaching a second
provider is a toolset naming it.

Nothing here knows an agent framework. That is what lets a declaration outlive
the framework that currently runs it, and what makes a contributor's specialist
a file rather than an integration.
"""

from dataclasses import dataclass
from typing import Any

from alert_triage.investigation.contract import Signal


@dataclass(frozen=True)
class Toolset:
    """A group of tools on one provider, and which of them a specialist may reach.

    Three parts, bounding three different things: the provider is looked up to
    find out where to connect and what authenticates there, the provider is
    asked for the group, and the framework is told the names within it. Only
    the last is ours to enforce if the provider regroups its tools.

    The provider is named rather than located. Which provider serves a toolset
    is part of the declaration and travels with it; where that provider is and
    what authenticates against it is a deployment's, and is supplied. That
    split is what lets one declaration run against two accounts unchanged —
    and, because each toolset names its own, what lets one specialist draw on
    two providers at once.

    Attributes:
        provider: Whose server groups these tools, as the deployment names it.
        name: The toolset as that provider groups it.
        tools: The tools within it this specialist is permitted to call.
    """

    provider: str
    name: str
    tools: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject a toolset that reaches nothing, which is a silent specialist."""
        if not self.provider.strip():
            raise ValueError(
                "A toolset needs the provider serving it: without one there is no "
                "server to ask for the group"
            )
        if not self.name.strip():
            raise ValueError("A toolset needs the name the provider groups it under")
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
        instruction: What it is asked to look for, in the terms of the
            providers it queries. Provider-specific by necessity: a query
            dialect does not translate, and pretending otherwise is what an
            earlier slice undid. Naming its providers per toolset does not make
            a declaration portable — it makes it able to reach more than one.
        output_schema: The shape it reports in. It has no free-text evidence
            field; it cites what it was shown.
        toolsets: What it may reach, and nothing else — each naming the
            provider that serves it, which may differ between them.
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
