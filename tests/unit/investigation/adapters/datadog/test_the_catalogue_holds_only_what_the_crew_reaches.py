"""The catalogue holds each tool the crew reaches, once, and nothing else.

A tool nobody permits is a description nobody reads, and one that drifts
unnoticed because no instruction ever renders it. Both Preview branches count:
a Preview tool is permitted by the declaration an account with access gets,
whatever this deployment's switch says.
"""

from alert_triage.investigation.adapters.crew.specialists.apm import apm_specialist
from alert_triage.investigation.adapters.crew.specialists.infrastructure import (
    INFRASTRUCTURE_SPECIALIST,
)
from alert_triage.investigation.adapters.crew.specialists.logs import (
    LOGS_SPECIALIST,
)
from alert_triage.investigation.adapters.crew.specialists.trace import (
    trace_specialist,
)
from alert_triage.investigation.adapters.datadog.tools import EVERY_TOOL

EVERY_DECLARATION = (
    LOGS_SPECIALIST,
    INFRASTRUCTURE_SPECIALIST,
    apm_specialist(preview=False),
    apm_specialist(preview=True),
    trace_specialist(preview=False),
    trace_specialist(preview=True),
)

PERMITTED_ANYWHERE = {
    tool
    for declaration in EVERY_DECLARATION
    for toolset in declaration.toolsets
    for tool in toolset.tools
}


def test_no_two_tools_share_a_name() -> None:
    names = [tool.name for tool in EVERY_TOOL]

    assert len(names) == len(set(names))


def test_every_tool_is_one_some_specialist_permits() -> None:
    assert {tool.name for tool in EVERY_TOOL} <= PERMITTED_ANYWHERE


def test_every_tool_a_specialist_permits_is_in_the_catalogue() -> None:
    """The other direction: a name typed outside it is a fact stated twice."""
    assert {tool.name for tool in EVERY_TOOL} >= PERMITTED_ANYWHERE
