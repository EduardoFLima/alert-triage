"""Datadog's addresses for what a retrieval returned, at both grains.

The platform half of a link. Nothing here reasons about evidence and nothing
here is reached by the framework adapter: a builder bound to a site is handed
across at composition, which is what lets a second platform's specialist bring
its own addresses without this file being edited.

Only forms Datadog documents are built. A retrieval is addressed as the Log
Explorer search that produced it — a query, the window it ran over as
millisecond timestamps, and a view pinned to that window rather than to the
present. An entry the payload identifies is addressed as that same search with
the entry named on it, so an address that cannot open the entry still opens the
search the entry is in. A link that degrades to the right page is the whole
point: the broken link this replaced degraded to nowhere.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

LOG_EXPLORER_PATH = "logs"

ENTRY_KEYS = ("id", "log_id", "event_id")
"""Where a retrieved entry's own identifier is found, where it has one.

Which of these a live payload actually uses is what the credential-gated run
answers. An entry under none of them is addressed as its retrieval, which is
why the list being incomplete costs precision rather than a working link.
"""

QUERY_KEYS = ("query", "filter_query", "search_query")
"""What the tool called the log query it was given."""

FROM_KEYS = ("from", "from_ts", "start", "filter_from")
TO_KEYS = ("to", "to_ts", "end", "filter_to")
"""What the tool called the ends of the window it searched."""

SECONDS_CEILING = 1e11
"""Above this an epoch value is milliseconds, below it seconds.

Roughly the year 5138 in seconds and 1973 in milliseconds: no window either
tool is called with lands in the gap, so the two are told apart without asking
the caller which it meant.
"""


class DatadogLinks:
    """Where the evidence one account returned is opened, bound to its site."""

    def __init__(self, site: str) -> None:
        """Bind the addresses to one deployment's account.

        Args:
            site: Datadog regional site, e.g. ``datadoghq.eu``. An account on
                one site addressed on another gets a page it cannot see.
        """
        self._site = site

    def to_retrieval(self, args: Mapping[str, Any]) -> str | None:
        """Where the search one retrieval came from is opened.

        Args:
            args: What the tool was called with. The query and the window are
                read out of it; what cannot be read is left off rather than
                guessed.

        Returns:
            The Log Explorer address for that search.
        """
        parameters: dict[str, str] = {"query": _first(args, QUERY_KEYS) or ""}
        window = _window(args)
        if window is not None:
            parameters["from_ts"], parameters["to_ts"] = window
        parameters["live"] = "false"
        return f"https://app.{self._site}/{LOG_EXPLORER_PATH}?{urlencode(parameters)}"

    def to_item(self, payload: Any, within: str | None) -> str | None:
        """Where one retrieved entry is opened.

        Args:
            payload: The entry as the platform returned it.
            within: Where the retrieval it came from is opened, which is what
                an entry the payload does not identify falls back to.

        Returns:
            The address of that entry, of the retrieval it came from, or
            ``None`` where the platform offers neither.
        """
        entry = _first(payload, ENTRY_KEYS) if isinstance(payload, dict) else None
        if entry is None:
            return within
        search = within or self.to_retrieval({})
        return f"{search}&{urlencode({'event': entry})}"


def _first(source: Any, keys: tuple[str, ...]) -> str | None:
    """The first of these keys the source carries a usable value under."""
    if not isinstance(source, Mapping):
        return None
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _window(args: Mapping[str, Any]) -> tuple[str, str] | None:
    """The window a retrieval ran over, as the explorer expresses one.

    Both ends or neither: an address carrying one end of a window shows a
    reader a period the evidence was not gathered over, which is a link to the
    wrong thing rather than a link to less.
    """
    start = _milliseconds(_end_of(args, FROM_KEYS))
    end = _milliseconds(_end_of(args, TO_KEYS))
    if start is None or end is None:
        return None
    return str(start), str(end)


def _end_of(args: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    """What the tool was told one end of its window was, under any of its names."""
    for key in keys:
        value = args.get(key)
        if value is not None:
            return value
    return None


def _milliseconds(value: Any) -> int | None:
    """One end of a window as the explorer expresses it, or ``None`` if unreadable.

    A model calls a tool with what the tool's own schema asks for, which is an
    instant in some accounts and an epoch in others. A value that is neither is
    left to the caller to drop.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return _scaled(float(value))
    if not isinstance(value, str):
        return None
    try:
        return _scaled(float(value))
    except ValueError:
        pass
    try:
        return int(datetime.fromisoformat(value).timestamp() * 1000)
    except ValueError:
        return None


def _scaled(value: float) -> int:
    """An epoch value in whichever unit it was given, expressed in milliseconds."""
    return int(value if value >= SECONDS_CEILING else value * 1000)
