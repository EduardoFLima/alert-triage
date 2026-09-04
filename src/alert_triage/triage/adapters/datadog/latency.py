"""Reading, out of a monitor's own account of itself, what it fired at.

Datadog states why a monitor triggered in prose written by whoever configured
it, so there is no field to read and no schema to rely on. What is here reads
that prose and is deliberately timid about it: it takes a number carrying a
time unit, only where the surrounding words call it a latency, and only where
exactly one such figure is on offer. Anything else yields nothing.

The timidity is not caution for its own sake — the cost of being wrong runs one
way. A latency this misses costs an investigation nobody needed. A latency this
invents silences an incident that mattered, and nobody finds out.
"""

import re

MILLISECONDS_PER = {
    "us": 0.001,
    "µs": 0.001,
    "microsecond": 0.001,
    "microseconds": 0.001,
    "ms": 1.0,
    "millisecond": 1.0,
    "milliseconds": 1.0,
    "s": 1000.0,
    "sec": 1000.0,
    "secs": 1000.0,
    "second": 1000.0,
    "seconds": 1000.0,
}
"""The time units a figure may be stated in, and what one of each is worth.

A unit absent from here is a unit this has not been shown to read, which yields
nothing rather than a guess: minutes are not a latency anybody states, and a
bare number is not a duration at all.
"""

LATENCY_WORDS = ("latency", "response time", "duration", "took")
"""What the surrounding text must say for a duration to be a latency.

Without this a monitor reporting "recovered after 30s" would hand over a figure
that is not a measurement of the service at all. A number is only a latency
where the account says it is one.
"""

_MEASUREMENT = re.compile(
    r"(?P<figure>\d+(?:\.\d+)?)\s*(?P<unit>[a-zµ]+)\b", re.IGNORECASE
)


def read_latency_ms(account: str | None) -> int | None:
    """Read the latency a monitor says it fired at, in milliseconds.

    Args:
        account: What the platform said about the alert, or ``None`` where it
            said nothing.

    Returns:
        The latency in milliseconds, or ``None`` wherever this cannot be sure:
        no account, no figure, a figure the text does not call a latency, a
        figure with no unit or one this does not read, or more than one
        candidate — an account offering both a measurement and the threshold it
        crossed states no single latency, and picking one of them would be a
        guess.
    """
    if not account:
        return None
    candidates = {
        milliseconds
        for line in account.splitlines()
        for milliseconds in _stated_in(line)
    }
    if len(candidates) != 1:
        return None
    return candidates.pop()


def _stated_in(line: str) -> list[int]:
    """The latencies one line states, in milliseconds. Usually none."""
    if not _about_latency(line):
        return []
    return [
        milliseconds
        for match in _MEASUREMENT.finditer(line)
        if (milliseconds := _as_milliseconds(match)) is not None
    ]


def _about_latency(line: str) -> bool:
    """Whether this line is talking about how long something took."""
    said = line.lower()
    return any(word in said for word in LATENCY_WORDS)


def _as_milliseconds(match: re.Match[str]) -> int | None:
    """One figure and its unit as milliseconds, or nothing for a unit unread."""
    per = MILLISECONDS_PER.get(match["unit"].lower())
    if per is None:
        return None
    return round(float(match["figure"]) * per)
