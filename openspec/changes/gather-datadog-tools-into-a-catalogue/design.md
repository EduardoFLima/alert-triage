## Context

See proposal.md for what is scattered and where. `Toolset` in
`investigation/domain/specialist.py` is the domain's view — provider, toolset
name, tool names — and stays as it is. Specialist tests mostly assert literal
tool names, so they catch an accidental rename.

## Goals / Non-Goals

**Goals:**
- Each tool's name, toolset and description stated once.
- A specialist's toolsets and its tool list in the instruction built from the
  same values, so they cannot disagree.

**Non-Goals:** see the proposal's out-of-scope list.

## Decisions

**A class for a tool, a module for the catalogue.** A frozen dataclass
`DatadogTool(name, toolset, description)` holds what travels together. The
catalogue is `datadog/tools.py`: toolset name constants (`CORE`, `KUBERNETES`,
`APM`) and one module-level constant per tool, grouped by toolset. An `Enum`
was considered; it adds nothing a frozen constant lacks and makes a tuple of
fields awkward to read. A class per toolset was considered too; toolsets have
no behaviour, only a name.

**It lives in `datadog/`, not `crew/`.** `AGENTS.md` places a provider's
server, addressing and grammar in `datadog/`, and a tool catalogue is the same
kind of fact. Declarations stay in `crew/` and import from it, as they already
import `DATADOG` and the dialect.

**Two helpers, in the same module.**

- `toolsets(*tools) -> tuple[Toolset, ...]` groups tools by toolset in first-
  seen order, with `provider=DATADOG`. A declaration can no longer put a tool
  in the wrong toolset, and the four hand-built `Toolset(...)` calls go.
- `described(*tools) -> str` renders the bullet list the instructions use
  today: ``- `name` description``.

**Descriptions say what a tool does, not how a specialist should use it.**
Where a specialist adds its own guidance today — infrastructure's "a host tag
narrows it to one host", APM's "ask the catalogue about that service and not
its neighbours" — that sentence stays in the specialist's instruction, after
the rendered list. That keeps the shared description true for every caller.

**Preview stays where it is.** `apm.py` and `trace.py` already choose tools by
`APM_TOOLSET_AVAILABLE`; they now choose catalogue values instead of names.
The catalogue records that those tools are in `APM`, which is the fact it owns.

## Risks / Trade-offs

- [Merged descriptions change what the model reads] → Keep today's wording
  wherever the specialists already agree; list every sentence moved in the
  commit message; run the live suite once (credential-gated, the user runs it).
- [A catalogue grows tools nobody declares] → Only tools some specialist
  permits are added; a unit test checks every catalogue tool is used.

## Migration Plan

Test first for the catalogue and its helpers, then one specialist per commit,
each with its existing tests green. Rollback is reverting the commits.
