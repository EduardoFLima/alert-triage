## Context

Specialists reach `list_datadog_skills` and `load_datadog_skill` through the
`core` toolset, and `CONSULT_THE_PLATFORM` tells them to browse. `build_agent`
passes `specialist.instruction` to the agent verbatim. `build_investigator` in
`app/composition.py` assembles the deployment once per run, synchronously,
before any alert is fetched. A run is one process (`app/main.py`). See
proposal.md for why.

ADK 2.7.1's `SkillToolset` (`google/adk/tools/skill_toolset.py`) takes
in-memory `Skill` objects. With `list_skills` filtered out, it adds their names
and descriptions to the prompt itself, and `load_skill` returns a skill's text
or `SKILL_NOT_FOUND` for a name it does not hold.

## Goals / Non-Goals

**Goals:**
- Guidance a specialist is offered follows from its tool list, with nothing to
  edit by hand.
- No guide text in an agent's context until that agent loads it.
- Guides come from Datadog at run start and live only in memory.

**Non-Goals:** see the proposal's out-of-scope list.

## Decisions

**Fetch at startup, in `build_investigator`.** It already runs once per run,
before any alert is fetched, and is where the deployment is assembled. It is
synchronous, so the fetch runs under one `asyncio.run`. The alternative,
fetching on the first investigation, spares runs with no incidents the cost,
but the user chose startup: it keeps the fetch out of the investigation path
and its bounds.

**Fetch through ADK's MCP toolset, not the `mcp` client directly.** An
`McpToolset` filtered to the two skill tools, with the connection
`connection_for` already builds, bounded by `mcp_call_timeout_seconds`. Using
`mcp` directly would be a second way of reaching the same server and a new
direct dependency to add to `.importlinter`.

**Serve guides with `SkillToolset`, filtered to `load_skill` and
`load_skill_resource`.** It gives the menu, the on-demand load, and refusal of
an unheld name without code of ours. It is not in any declaration, so
`log_tool_call` and `keep_evidence_callback` already pass it through untouched:
no budget, no evidence, no failed retrieval. The alternatives were our own menu
and local load tool (more code for the same result), or keeping
`load_datadog_skill` (every load a server call, counted as evidence, and
nothing refusing an off-menu guide). Its registry mode was rejected too: it
fetches on demand, but then the prompt lists no menu and the model has to use
`search_skills`, which is browsing again.

**References are loaded with their guide.** Where a guide names a further
reference, it is fetched at startup into `Resources.references` under the path
the guide used, and served by `load_skill_resource`. One level, so a guide
cannot pull the whole library in by chaining.

**Match a guide to a specialist by tool name.** A guide is offered to a
specialist when its text names, as a whole word, any tool in that specialist's
permitted set. The alternative — a hand-kept map of guide name to specialist —
is what the proposal rejects. The rule lives in `adapters/datadog/`, because
what a guide looks like is the provider's; building `Skill` objects lives in
`adapters/adk/`.

**Rename a guide to a name ADK accepts.** `Frontmatter` requires kebab-case. A
Datadog name that is not (for example `datadog/metrics`) is turned into one
(`datadog-metrics`) in `adapters/datadog/`. The model only ever sees the ADK
name, so nothing maps it back.

**Preview guides follow the Preview switch for free.** While
`APM_TOOLSET_AVAILABLE` is off, no specialist permits an `apm` tool, so a guide
covering only those tools is offered to no one. When the switch flips, the
widened declarations pick it up with no further edit.

**Supply guides to the deployment, not the declaration.** `Deployment` gains
the fetched guides; `build_agent` matches them to the specialist and adds a
`SkillToolset` when there is at least one. `Specialist` gains no field:
guidance is a deployment fact supplied to a declaration, as the existing
requirement demands. `test_a_declaration_and_its_instruction_agree` is
unaffected, because neither the menu nor the load tools are in a declaration.

**Missing guidance is a warning, not a failure.** If the fetch fails, the run
continues with no guides and one log line. Re-granting the Datadog skill tools
as a fallback was rejected: it brings back browsing.

## Risks / Trade-offs

- [ADK adds a generic skills instruction to every model call, ~400 tokens,
  mentioning scripts and "report the error to the user"] → Accepted for now.
  Measure it on the live run; overriding `process_llm_request` is a separate
  change if it earns one.
- [A guide never names its tools, so no specialist is offered it] → The live
  suite asserts each specialist is offered at least one guide. It skips
  without credentials; it has to be run by hand once.
- [A loaded guide mentions a neighbouring tool] → A tool call the filter
  refuses; the menu's descriptions steer toward the right guide. Watch for it
  on the live run.
- [A specialist skips the guide and writes a bad query anyway] → ADK's own
  instruction tells it to load a relevant skill first. Record loads on the live
  run.
- [Startup reads every guide, even on runs with no incidents] → One call per
  guide and reference per run. Accepted in exchange for a fetch outside the
  investigation's bounds.
- [`SkillToolset` changes shape in a later ADK 2.x] → It is used in one place,
  `adapters/adk/`, and covered by unit tests against the installed version.

## Migration Plan

One commit per behaviour, test first. The grammar in `METRIC_QUERY_DIALECT`
stays until a live run shows the metrics guide covers it. Rollback is reverting
the change: the Datadog skill tools come back into the toolsets.

## Open Questions

- What the listing gives for a guide's name and description, and how a guide
  names a further reference. Settled by reading one real listing and guide; the
  design holds either way.
