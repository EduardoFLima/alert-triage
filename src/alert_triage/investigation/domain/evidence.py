"""The citation discipline: what a finding may be built on, and what is dropped.

An instruction telling an agent to cite its evidence is a request, and a model
can satisfy it with text that looks exactly like a log line and never existed.
Nothing downstream could tell the difference. So a finding is built only from
citations that resolve to something actually retrieved: an identifier the model
invents resolves to nothing, and a finding left with no evidence is dropped —
logged, so that a fabricating model is visible to whoever is tuning it, and
dropped alone, so its honest siblings still reach the team.

A failed retrieval is the other half of the discipline, and the more dangerous
half. "The service logged nothing" and "the search failed" are opposite
findings, and a model reading the second as the first is the misreading
``RETRIEVAL_FAILED`` exists to prevent.

What this does *not* verify is the model's characterisation. ``observation``
and ``occurrences`` are its own prose and its own arithmetic; the evidence
travels beside them precisely so a reader can see the two disagree.

The discipline is stated here, against whatever kept the evidence: how a tool
result is retained and keyed is the adapter's business, and this only ever asks
it to resolve a citation.
"""

import logging
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from alert_triage.investigation.contract import EvidenceItem, Finding, Findings, Signal

_log = logging.getLogger(__name__)

RETRIEVAL_FAILED = (
    "This retrieval failed. It returned no evidence, and it is not an empty "
    "result: nothing about the service may be concluded from it, in either "
    "direction. Do not cite it, and do not report the service as quiet on the "
    "strength of it. Try a different retrieval, or report what the retrievals "
    "that succeeded show."
)
"""What a specialist is handed in place of a failed tool result.

Deliberately verbose. The one thing that must not happen is a model reading a
failure as a search that came back clean, and a terse error string is exactly
what invites that reading.
"""


class Citable(Protocol):
    """What this investigation was shown, asked whether a citation resolves."""

    def resolve(self, citation: str) -> EvidenceItem | None:
        """The evidence behind a citation, or ``None`` if there is none."""
        ...


def findings_from(
    payloads: Iterable[Any], retrieved: Citable, signal: Signal
) -> Findings:
    """Build findings from what a specialist reported, keeping only what checks out.

    Args:
        payloads: What the agent produced, one entry per finding.
        retrieved: What this investigation actually retrieved.
        signal: The dimension the specialist that reported these looked at.

    Returns:
        The findings whose evidence resolves. Empty findings mean nothing the
        agent said survived checking, which is reported as an investigation
        that found nothing notable rather than as a failure: it did run.
    """
    built = [_finding(payload, retrieved, signal) for payload in payloads]
    return Findings(findings=tuple(one for one in built if one is not None))


def _finding(payload: Any, retrieved: Citable, signal: Signal) -> Finding | None:
    """Build one finding, or drop it and say why."""
    if not isinstance(payload, dict):
        _log.warning("Discarding a finding that is not a record: %r", payload)
        return None

    observation = str(payload.get("observation", "")).strip()
    if not observation:
        _log.warning("Discarding a finding that observes nothing")
        return None

    examples = _examples(payload.get("cites", ()), retrieved, observation)
    if not examples:
        _log.warning(
            "Discarding the finding %r: none of its evidence was ever retrieved",
            observation,
        )
        return None

    return Finding(
        signal=signal,
        observation=observation,
        occurrences=max(_occurrences(payload), len(examples)),
        examples=examples,
    )


def _examples(
    cites: Any, retrieved: Citable, observation: str
) -> tuple[EvidenceItem, ...]:
    """Resolve citations into the evidence behind them, dropping the invented."""
    if not isinstance(cites, Sequence) or isinstance(cites, str):
        return ()
    resolved = []
    for citation in cites:
        evidence = retrieved.resolve(str(citation))
        if evidence is None:
            _log.warning(
                "The finding %r cited %r, which was never retrieved",
                observation,
                citation,
            )
            continue
        resolved.append(evidence)
    return tuple(resolved)


def _occurrences(payload: dict[str, Any]) -> int:
    """How often the model says the pattern occurred, defaulting to nothing.

    A count that comes back unreadable is not worth failing a finding for: the
    evidence is what was checked, and the caller raises the count to at least
    the number of items shown so the finding cannot contradict itself.
    """
    raw = payload.get("occurrences")
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else 0
