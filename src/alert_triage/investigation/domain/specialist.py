from dataclasses import dataclass
from typing import Any

from alert_triage.investigation.contract import Signal


@dataclass(frozen=True)
class Toolset:
    provider: str
    name: str
    tools: tuple[str, ...]

    def __post_init__(self) -> None:
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
    name: str
    signal: Signal
    instruction: str
    output_schema: type[Any]
    toolsets: tuple[Toolset, ...]
    model: str | None = None

    def __post_init__(self) -> None:
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
