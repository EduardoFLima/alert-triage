"""Why a report can never quote a log line that was never logged.

An instruction telling an agent to cite its evidence is a request, and a model
can satisfy it with text that looks exactly like a log line and never existed.
Nothing downstream could tell the difference.

So the model is never given the chance to write evidence. Every record the
platform returns passes through ``Retrieved``, which hands the model a copy
under an identifier and keeps the real record. The agent's output schema has
no free-text evidence field: it cites identifiers. Resolving those citations
back into ``LogRecord`` values is what builds a finding, so the log lines a
human reads are assembled here out of what the platform actually sent.

An identifier the model invents resolves to nothing, and a finding left with
no evidence is dropped — logged, so that a fabricating model is visible to
whoever is tuning it, and dropped alone, so its honest siblings still reach
the team.

What this does *not* verify is the model's characterisation. ``observation``
and ``occurrences`` are its own prose and its own arithmetic; the records
travel beside them precisely so a reader can see the two disagree.
"""

import logging
from collections.abc import Iterable, Sequence
from typing import Any

from alert_triage.domain.findings import Finding, Findings, LogRecord, Signal

_log = logging.getLogger(__name__)

_CITATION_PREFIX = "rec_"


class Retrieved:
    """The records this investigation actually retrieved, keyed for citation.

    One instance per investigation. It is deliberately stateful and short
    lived: what may be cited is exactly what this investigation was shown, so
    a stale identifier from an earlier incident cannot resolve.
    """

    def __init__(self) -> None:
        """Start with nothing retrieved and nothing citable."""
        self._records: dict[str, LogRecord] = {}

    def offer(self, records: Iterable[LogRecord]) -> list[dict[str, Any]]:
        """Keep these records and describe them for the model.

        Args:
            records: What a search returned.

        Returns:
            One dictionary per record, carrying the identifier the model cites
            it by alongside the fields it needs to reason about the line.
        """
        offered = []
        for record in records:
            identifier = f"{_CITATION_PREFIX}{len(self._records) + 1}"
            self._records[identifier] = record
            offered.append(
                {
                    "id": identifier,
                    "timestamp": record.timestamp.isoformat(),
                    "level": record.level,
                    "message": record.message,
                    "service": record.service,
                }
            )
        return offered

    def resolve(self, citation: str) -> LogRecord | None:
        """The real record behind a citation, or ``None`` if there is none."""
        return self._records.get(citation)


def findings_from(payloads: Iterable[Any], retrieved: Retrieved) -> Findings:
    """Build findings from what the model reported, keeping only what checks out.

    Args:
        payloads: What the agent produced, one entry per finding.
        retrieved: The records this investigation actually retrieved.

    Returns:
        The findings whose evidence resolves. Empty findings mean nothing the
        agent said survived checking, which is reported as an investigation
        that found nothing notable rather than as a failure: it did run.
    """
    built = [_finding(payload, retrieved) for payload in payloads]
    return Findings(findings=tuple(one for one in built if one is not None))


def _finding(payload: Any, retrieved: Retrieved) -> Finding | None:
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
        signal=Signal.LOGS,
        observation=observation,
        occurrences=max(_occurrences(payload), len(examples)),
        examples=examples,
    )


def _examples(
    cites: Any, retrieved: Retrieved, observation: str
) -> tuple[LogRecord, ...]:
    """Resolve citations into the records behind them, dropping the invented."""
    if not isinstance(cites, Sequence) or isinstance(cites, str):
        return ()
    resolved = []
    for citation in cites:
        record = retrieved.resolve(str(citation))
        if record is None:
            _log.warning(
                "The finding %r cited %r, which was never retrieved",
                observation,
                citation,
            )
            continue
        resolved.append(record)
    return tuple(resolved)


def _occurrences(payload: dict[str, Any]) -> int:
    """How often the model says the pattern occurred, defaulting to nothing.

    A count that comes back unreadable is not worth failing a finding for: the
    evidence is what was checked, and the caller raises the count to at least
    the number of records shown so the finding cannot contradict itself.
    """
    raw = payload.get("occurrences")
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else 0
