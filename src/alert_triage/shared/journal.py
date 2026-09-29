"""Vocabulary for log blocks, not the policy for when to write them."""

import textwrap
from collections.abc import Iterator, Mapping

WIDTH = 64
"""Narrow enough for split terminals and pasted incident notes."""

_INDENT = "  "
_GAP = 3
_BLOCK_LENGTH = 160
"""Beyond this, values get their own lines rather than a cramped column."""

_DEFAULT_LIMIT = 240


def banner(title: str, subject: str | None = None, /, **details: object) -> str:
    heading = f"{title} · {subject}" if subject else title
    width = max(WIDTH, len(heading) + 4)
    return _written(
        [
            f"╭{'─' * (width - 2)}╮",
            f"│ {heading.ljust(width - 3)}│",
            f"╰{'─' * (width - 2)}╯",
            *_detailed(details, width),
        ]
    )


def event(caption: str, body: str | None = None, /, **details: object) -> str:
    return _written(
        [
            f"{_INDENT}── {caption} {'─' * max(0, WIDTH - len(caption) - 6)}",
            *(_paragraphs(body, WIDTH, _INDENT) if body else ()),
            *_detailed(details, WIDTH),
        ]
    )


def shortened(value: object, limit: int = _DEFAULT_LIMIT) -> str:
    """Shorten pass-through platform values, not the run's reasoning."""
    said = " ".join(str(value).split())
    if len(said) <= limit:
        return said
    kept = said[:limit]
    boundary = kept.rfind(" ")
    if boundary > limit // 2:
        kept = kept[:boundary]
    return f"{kept}… [{len(said) - len(kept)} more characters]"


def _written(lines: list[str]) -> str:
    """Open under the log prefix; the handler owns the blank line after it."""
    while lines and not lines[-1]:
        lines.pop()
    return "\n" + "\n".join(lines)


def _detailed(details: Mapping[str, object], width: int) -> Iterator[str]:
    stated = {
        label.replace("_", " "): said
        for label, value in details.items()
        if (said := "" if value is None else str(value).strip())
    }
    if not stated:
        return
    column = max(len(label) for label in stated) + _GAP
    for label, said in stated.items():
        if "\n" in said or len(said) > _BLOCK_LENGTH:
            yield f"{_INDENT}{label}"
            yield from _paragraphs(said, width, _INDENT * 2)
        else:
            yield from _wrapped(
                said, width, f"{_INDENT}{label.ljust(column)}", len(_INDENT) + column
            )


def _paragraphs(said: str, width: int, indent: str) -> Iterator[str]:
    for paragraph in said.strip().split("\n\n"):
        yield from _wrapped(paragraph, width, indent, len(indent))
        yield ""


def _wrapped(said: str, width: int, opening: str, hanging: int) -> Iterator[str]:
    yield from textwrap.wrap(
        " ".join(said.split()),
        width=width,
        initial_indent=opening,
        subsequent_indent=" " * hanging,
        break_on_hyphens=False,
        break_long_words=False,
    ) or [opening.rstrip()]
