"""An agent that reasons over what the specialists brought back, declared as data.

A reasoner is its name, what it is instructed to do, the shape of what it
produces, and — where it differs from its siblings — the model it runs on. What
it is *not* is a specialist: it reaches no observability platform, composes no
query, and gathers no evidence.

That is why this is a type of its own rather than a ``Specialist`` with an empty
toolset. What an APM agent is includes what it may ask, and that invariant is
enforced by a declaration that refuses to exist without tools. Relaxing it so a
toolless agent could pass would cost every specialist the guarantee in order to
describe two agents that were never specialists.

The Diagnostician does reach tools, but its tools are the crew, supplied where
it is built rather than declared here. A specialist's reach is its identity; a
manager's reach is whichever specialists a deployment happens to run.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Reasoner:
    """One reasoning agent, declared whole.

    Attributes:
        name: What this reasoner is called, in the agent and in configuration.
        instruction: What it is asked to do with what it is given.
        output_schema: The shape it answers in.
        model: The model it reasons on, or ``None`` to take the deployment's
            default.
    """

    name: str
    instruction: str
    output_schema: type[Any]
    model: str | None = None

    def __post_init__(self) -> None:
        """Reject a declaration that could not run as one."""
        if not self.name.strip():
            raise ValueError("A reasoner needs a name to be configured and logged by")
        if not self.instruction.strip():
            raise ValueError(
                "A reasoner needs an instruction: without one it reasons about nothing"
            )
