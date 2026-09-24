"""A section a specialist named reaches the finding, and one it made up does not.

The schema already bounds what a model may answer, but a report crosses an
agent-tool hop as a plain record, so the discipline is enforced again where a
finding is built: a member of the set is kept, and anything else is no section.
"""

from typing import Any

import pytest

from alert_triage.investigation.contract import EvidenceItem, Section, Signal
from alert_triage.investigation.domain.evidence import findings_from


class _Retained:
    def resolve(self, citation: str) -> EvidenceItem | None:
        return EvidenceItem(id=citation, instant=None, summary="rolled", payload={})


def _section_of(reported: dict[str, Any]) -> Section | None:
    payload = {"observation": "rolled out", "occurrences": 1, "cites": ["call-1"]}
    (finding,) = findings_from(
        [payload | reported], _Retained(), Signal.INFRASTRUCTURE
    ).findings
    return finding.section


def test_a_section_from_the_set_is_kept() -> None:
    assert _section_of({"section": "infrastructure"}) is Section.INFRASTRUCTURE


@pytest.mark.parametrize("unrecognised", ["the graphs tab", "", 7, None, ["logs"]])
def test_a_section_outside_the_set_is_no_section(unrecognised: object) -> None:
    """Treated as absent rather than refused: the finding itself still stands."""
    assert _section_of({"section": unrecognised}) is None


def test_a_finding_naming_no_section_has_none() -> None:
    assert _section_of({}) is None
