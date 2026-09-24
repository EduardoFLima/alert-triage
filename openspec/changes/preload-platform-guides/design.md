## Context

Specialists reach `list_datadog_skills` and `load_datadog_skill` through the
`core` toolset, and `CONSULT_THE_PLATFORM` tells them to browse. `build_agent`
passes `specialist.instruction` to the agent verbatim. A run is one process
(`app/main.py`); each investigation calls `asyncio.run` inside the closure
`run_with_adk(deployment)` returns. See proposal.md for why.

## Goals / Non-Goals

**Goals:**
- Guidance a specialist sees follows from its tool list, with nothing to edit
  by hand.
- The specialist declarations stay framework- and fetch-free data.

**Non-Goals:**
- Filtering a guide's text down to permitted tools. A guide is given whole.
- Caching guides across runs.

## Decisions

**Load once per run, on the first investigation.** The closure from
`run_with_adk` fetches the guides the first time it runs and keeps them for the
rest of the run. The alternative, fetching in `build_investigator`, would put
async I/O in the composition root and pay for it on runs with no incidents.
Since a run is one short process, "once per run" and "at startup" mean the same
freshness.

**Fetch through ADK's MCP toolset, not the `mcp` client directly.** An
`McpToolset` filtered to the two skill tools, with the same connection
`connection_for` already builds, and bounded by `mcp_call_timeout_seconds`.
Using `mcp` directly would be a second way of reaching the same server and a
new direct dependency to add to `.importlinter`.

**Match a guide to a specialist by tool name.** A guide is given to a
specialist when its text names, as a whole word, any tool in that specialist's
permitted set. The alternative — a hand-kept map of guide name to specialist —
is what the proposal rejects. The rule lives in `adapters/datadog/`, because
what a guide looks like is the provider's; the fetch lives in `adapters/adk/`.

**Guides follow references one level deep.** Where a matched guide names a
further reference (the current `CONSULT_THE_PLATFORM` says they do), that
reference is loaded and appended. One level, so a guide cannot pull the whole
library in by chaining.

**Preview guides follow the Preview switch for free.** While
`APM_TOOLSET_AVAILABLE` is off, no specialist permits an `apm` tool, so a guide
covering only those tools is matched to no one. When the switch flips, the
widened declarations pick the guide up with no further edit.

**Compose, don't mutate, the declaration.** `build_agent` takes the matched
guidance and sets the agent's instruction to the declaration's instruction
followed by the guides. `Specialist` gains no field: guidance is a deployment
fact supplied to a declaration, as the existing requirement demands.

**Missing guidance is a warning, not a failure.** If the fetch fails, the run
continues with an empty guidance map and logs once. Re-granting the skill tools
as a fallback was considered and rejected: it brings back the problem this
change removes.

## Risks / Trade-offs

- [A guide never names its tools, so no specialist is matched to it] → The live
  suite asserts each specialist is matched to at least one guide. It skips
  without credentials; it has to be run by hand once.
- [A matched guide still mentions a neighbouring tool] → One line in the shared
  instruction: guides may mention tools you do not have; call only yours. This
  deliberately stops short of the discipline
  `test_a_declaration_and_its_instruction_agree` holds a declaration to — that
  an instruction names no tool a sibling owns. The check stays on the
  declaration; the composed instruction is runtime text it cannot see.
- [Longer instructions cost tokens on every model call] → Measure the guide
  sizes on the live run; if one is large, prefer the one-level cap over
  trimming text.
- [Datadog changes a guide and a query that worked starts failing] → That is the
  point: the grammar now tracks the platform instead of drifting from it.

## Migration Plan

One commit per behaviour, test first. `METRIC_QUERY_DIALECT` stays until a live
run shows the metrics guide covers every rule it teaches; then it is deleted in
its own commit. Rollback is reverting the change: the skill tools come back
into the toolsets.

## Open Questions

- What a guide's reference to a further guide looks like on the wire. The
  one-level rule holds either way; only the parsing depends on it, and it is
  settled by reading one real guide.
