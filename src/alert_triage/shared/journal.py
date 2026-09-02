"""How a run writes itself down, so that a human can read what it did.

A log line is the only account anybody has of a run that has already finished.
This is the vocabulary every context writes that account in: a *banner* for a
phase of the run, an *event* for a moment inside one, and details aligned
beneath either. Two weights and no more — a reader scrolling for the moment
something went wrong finds the phase by its box and the moment by its caption,
and a third weight would only blur the difference between them.

What went wrong is written in the same two weights, chosen by consequence
rather than by level: a failure that ends the run is boxed like the phase it
ended, because nothing after it will tell a reader why the log stops; a failure
contained to one group or one consultation is captioned under the phase it
happened in, because the run carries on around it. How bad it is stays where it
already was — the level, which every record carries.

Nothing here decides *what* is worth writing down. That belongs to the code
that knows what just happened; this decides only how it reads.

The shared kernel is the right home for it because it is vocabulary rather than
behaviour: the pipeline, the platform adapters, and the agent callbacks all
write the same account, and a reader should not be able to tell which of them
wrote which block.
"""

import textwrap
from collections.abc import Iterator, Mapping

WIDTH = 64
"""How wide a block is drawn, in characters.

Narrow enough to read in a split terminal and to survive a chat window someone
pastes it into, which is where an incident's log usually ends up.
"""

_INDENT = "  "
_GAP = 3
"""Space between the longest detail label and the column its values start in."""

_BLOCK_LENGTH = 160
"""Beyond this, a value is given its own lines rather than a label's column.

A hypothesis fits beside its label. What a specialist observed does not, and
squeezing it into a column against the right margin is how the one thing a
reader came for becomes the hardest thing to read.
"""

_DEFAULT_LIMIT = 240


def banner(title: str, subject: str | None = None, /, **details: object) -> str:
    """Announce a phase of a run, boxed so it cannot be scrolled past.

    Args:
        title: What is beginning or has just ended, stated in a few words.
        subject: What it concerns — a service, usually. Absent for a phase
            that concerns the whole run.
        **details: The facts of the phase, in the order they are worth reading.
            An underscored name reads as words; a value that is ``None`` or
            blank is left out, so a caller may pass what it may not have.

    Returns:
        The block, opening on a line of its own.
    """
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
    """Write down a moment within a phase, captioned rather than boxed.

    Args:
        caption: What happened, in a few words.
        body: What was said, where the moment is something an agent said. It
            is written under the caption in its own words, unlabelled.
        **details: The facts of the moment, treated as ``banner`` treats them.

    Returns:
        The block, opening on a line of its own.
    """
    return _written(
        [
            f"{_INDENT}── {caption} {'─' * max(0, WIDTH - len(caption) - 6)}",
            *(_paragraphs(body, WIDTH, _INDENT) if body else ()),
            *_detailed(details, WIDTH),
        ]
    )


def shortened(value: object, limit: int = _DEFAULT_LIMIT) -> str:
    """State something too long to read in full, and say what was left out.

    For values a run passes through rather than produces — a platform's answer,
    a tool's arguments. What an agent said is never shortened: it is the run's
    reasoning, and half of it is worse than none.

    Args:
        value: What to state, in whatever shape it arrived.
        limit: How many characters are worth reading here.

    Returns:
        The value on one line, cut at a word where it can be, with a note of
        how much was dropped. Short values are returned exactly as they read.
    """
    said = " ".join(str(value).split())
    if len(said) <= limit:
        return said
    kept = said[:limit]
    boundary = kept.rfind(" ")
    if boundary > limit // 2:
        kept = kept[:boundary]
    return f"{kept}… [{len(said) - len(kept)} more characters]"


def _written(lines: list[str]) -> str:
    """Set a block apart from the record whose timestamp and level introduce it.

    It opens on a line of its own so the box sits under that prefix rather than
    beside it, and it ends where its last line does: the blank line below every
    record belongs to the handler, which is the only place that can give a stack
    trace the same courtesy. The separator a paragraph leaves behind it is
    dropped for the same reason.
    """
    while lines and not lines[-1]:
        lines.pop()
    return "\n" + "\n".join(lines)


def _detailed(details: Mapping[str, object], width: int) -> Iterator[str]:
    """Lay the facts of a block out under it, aligned in one column."""
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
    """Everything that was said, kept whole and still in its own paragraphs."""
    for paragraph in said.strip().split("\n\n"):
        yield from _wrapped(paragraph, width, indent, len(indent))
        yield ""


def _wrapped(said: str, width: int, opening: str, hanging: int) -> Iterator[str]:
    """One value, wrapped so its continuation lines sit under where it began."""
    yield from textwrap.wrap(
        " ".join(said.split()),
        width=width,
        initial_indent=opening,
        subsequent_indent=" " * hanging,
        break_on_hyphens=False,
        break_long_words=False,
    ) or [opening.rstrip()]
