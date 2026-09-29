from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Reasoner:
    name: str
    instruction: str
    output_schema: type[Any]
    model: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("A reasoner needs a name to be configured and logged by")
        if not self.instruction.strip():
            raise ValueError(
                "A reasoner needs an instruction: without one it reasons about nothing"
            )
