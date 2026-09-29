import logging
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from alert_triage.investigation.contract import (
    EvidenceItem,
    Finding,
    Findings,
    Section,
    Signal,
)
from alert_triage.shared import journal

_log = logging.getLogger(__name__)

RETRIEVAL_FAILED = (
    "This retrieval failed. It returned no evidence, and it is not an empty "
    "result: nothing about the service may be concluded from it, in either "
    "direction. Do not cite it, and do not report the service as quiet on the "
    "strength of it. Try a different retrieval, or report what the retrievals "
    "that succeeded show."
)


class Citable(Protocol):
    def resolve(self, citation: str) -> EvidenceItem | None: ...


def findings_from(
    payloads: Iterable[Any], retrieved: Citable, signal: Signal
) -> Findings:
    built = [_finding(payload, retrieved, signal) for payload in payloads]
    return Findings(findings=tuple(one for one in built if one is not None))


def _finding(payload: Any, retrieved: Citable, signal: Signal) -> Finding | None:
    if not isinstance(payload, dict):
        _log.warning(
            journal.event(
                "a finding was discarded",
                because="it is not a record",
                reported=journal.shortened(repr(payload)),
            )
        )
        return None

    observation = str(payload.get("observation", "")).strip()
    if not observation:
        _log.warning(
            journal.event("a finding was discarded", because="it observes nothing")
        )
        return None

    examples = _examples(payload.get("cites", ()), retrieved, observation)
    if not examples:
        _log.warning(
            journal.event(
                "a finding was discarded",
                because="none of its evidence was ever retrieved",
                observation=observation,
            )
        )
        return None

    return Finding(
        signal=signal,
        observation=observation,
        occurrences=max(_occurrences(payload), len(examples)),
        examples=examples,
        section=_section(payload),
    )


def _section(payload: dict[str, Any]) -> Section | None:
    """A wrong tab is cheaper than discarding an otherwise evidenced finding."""
    named = payload.get("section")
    known = {section.value for section in Section}
    return Section(named) if isinstance(named, str) and named in known else None


def _examples(
    cites: Any, retrieved: Citable, observation: str
) -> tuple[EvidenceItem, ...]:
    if not isinstance(cites, Sequence) or isinstance(cites, str):
        return ()
    resolved = []
    for citation in cites:
        evidence = retrieved.resolve(str(citation))
        if evidence is None:
            _log.warning(
                journal.event(
                    "a citation resolved to nothing",
                    citation=repr(citation),
                    observation=observation,
                )
            )
            continue
        resolved.append(evidence)
    return tuple(resolved)


def _occurrences(payload: dict[str, Any]) -> int:
    raw = payload.get("occurrences")
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else 0
