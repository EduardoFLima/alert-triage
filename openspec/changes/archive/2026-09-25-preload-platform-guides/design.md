## Context

Specialists reach `list_datadog_skills` and `load_datadog_skill` through the
`core` toolset, and `CONSULT_THE_PLATFORM` tells them to browse. `build_agent`
passes `specialist.instruction` to the agent verbatim. `build_investigator` in
`app/composition.py` assembles the deployment once per run, synchronously,
before any alert is fetched. A run is one process (`app/main.py`). See
proposal.md for why.

ADK 2.7.1's `SkillToolset` (`google/adk/tools/skill_toolset.py`) takes
in-memory `Skill` objects, and `load_skill` returns a skill's text or
`SKILL_NOT_FOUND` for a name it does not hold. It adds their names and
descriptions to the prompt only when it has no `list_skills` tool — and it
checks the tools it was built with, not those its `tool_filter` leaves, so
filtering `list_skills` out does not bring the menu in.

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

**Fetch through ADK's MCP session manager, not the `mcp` client directly.** An
`MCPSessionManager` over the connection `connection_for` already builds, asked
for every toolset the crew reaches (a guide's visibility depends on the
toolsets requested), each call bounded by `mcp_call_timeout_seconds`. Not
`McpToolset`: calling one of its tools outside an agent needs a `ToolContext`
there is no invocation to build from. Using `mcp`'s transport directly would be
a second way of reaching the same server.

**One listing, then one load per guide, in sequence.** The listing with
`include_header` gives every guide's name, description and bundled references
in one call. Each guide's text is loaded one at a time; the server refuses a
burst (about 45 loads in quick succession) with an error result, so a refused
load is retried after a pause, a bounded number of times, and a guide still
refused is left out with a warning naming it. References are loaded only for
guides some specialist is offered, and guides offered to nobody are dropped.

**Serve guides with `SkillToolset`, filtered to `load_skill` and
`load_skill_resource`.** It gives the on-demand load and refusal of an
unheld name without code of ours. The menu takes a small subclass in
`adapters/adk/skills.py` that appends it in `process_llm_request`, using ADK's
own `format_skills_as_xml`, because the filter hides `list_skills` without the
toolset noticing (see Context). It is not in any declaration, so
`log_tool_call` and `keep_evidence_callback` already pass it through untouched:
no budget, no evidence, no failed retrieval. The alternatives were our own menu
and local load tool (more code for the same result), or keeping
`load_datadog_skill` (every load a server call, counted as evidence, and
nothing refusing an off-menu guide). Its registry mode was rejected too: it
fetches on demand, but then the prompt lists no menu and the model has to use
`search_skills`, which is browsing again.

**References are loaded with their guide.** A guide's references are the ones
the listing names for it, every one under `references/`. Each is fetched at
startup with `load_datadog_skill`'s `resource_path` and kept in
`Resources.references` under the path without that prefix, which is how
`load_skill_resource` looks it up. One level, so a guide cannot pull the whole
library in by chaining; the other guides a guide points to are not followed.

**Match a guide to a specialist by the tools it documents.** A guide is offered
to a specialist when it has a heading naming, as a whole word, a tool in that
specialist's permitted set (`### search_datadog_logs`). The first version
matched any mention in the text, and the live library showed it too broad:
database and LLM-observability playbooks name `search_datadog_logs` and
`get_datadog_metric` in passing, so every specialist was offered 9 to 23 guides
of up to 400k characters. By heading, each is offered the one to four guides
that document its tools. No guide has a heading for either skill tool, so the
match needs no exception for them while they are still permitted (until 4.2).
The
alternative — a hand-kept map of guide name to specialist — is what the
proposal rejects. The rule lives in `adapters/datadog/`, because what a guide
looks like is the provider's; building `Skill` objects lives in
`adapters/adk/`.

**A description too long for ADK is shortened.** `Frontmatter` refuses more
than 1024 characters, and some listed descriptions run to 1800. It is cut at a
word boundary with an ellipsis rather than the guide being dropped.

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
  guide (59 on the account read) plus the offered guides' references, per run:
  about twenty seconds on the account read, one pause for a refused burst
  included. Accepted in exchange for a fetch outside the investigation's
  bounds.
- [A guide's headings change shape] → The live suite asserts each specialist is
  offered at least one guide.
- [`SkillToolset` changes shape in a later ADK 2.x] → It is used in one place,
  `adapters/adk/`, and covered by unit tests against the installed version.

## Migration Plan

One commit per behaviour, test first. The grammar in `METRIC_QUERY_DIALECT`
stays until a live run shows the metrics guide covers it. Rollback is reverting
the change: the Datadog skill tools come back into the toolsets.

## What the platform publishes

Settled by reading the real listing and guides (task 2.1):

- `list_datadog_skills` with `include_header: true` returns one text block, a
  line per guide: `- **datadog/metrics**: <description> (related: …)`,
  optionally followed by `  Resources: references/a.md, references/b.md`.
- Names are `datadog/<name>`, sometimes nested (`datadog/dbm-mysql/investigate`),
  sometimes snake_case, and one is `generic`.
- `load_datadog_skill` takes `skill_name`, optionally `resource_path`, and
  requires `telemetry: {intent}` on every call, as does the listing. It returns
  markdown text; an unknown name or a refused burst comes back as an error
  result, not an exception.
- A guide documents its tools under a `## Tools` section, one `### <tool>`
  heading each.

## What the live run showed

Settled by the live suite and one measured run per specialist (tasks 5.1–5.3),
against the EU account with `gemini-2.5-flash`:

- Every specialist is offered at least one guide. Of the guides published, 8
  document a tool somebody on the crew holds:

  | Specialist | Offered | Loaded | Added instruction |
  |---|---|---|---|
  | logs | `logs` | `logs` | 2,368 chars, ~360 words |
  | apm | `advanced-products`, `metrics`, `resource-changes` | `metrics`, `advanced-products` | 3,068 chars, ~434 words |
  | trace | `traces` | `traces` | 2,272 chars, ~343 words |
  | infrastructure | `bulk-dpa-generator`, `kubernetes`, `metrics`, `services-and-infrastructure` | — (run failed, below) | 3,190 chars, ~453 words |

- "Added instruction" is everything the skill toolset appends: ADK's generic
  skills instruction plus the menu. It is in line with the ~400 tokens the
  risk above assumed, so no override of `process_llm_request` is earned yet.
- Every specialist that ran loaded a guide before querying, and none loaded a
  guide it was not offered or a `references/` file.
- `bulk-dpa-generator` (46 KB) is offered to the infrastructure specialist for
  naming a metrics tool under its `## Tools`. It is a menu entry, not a load,
  so it costs a line of the prompt; worth watching if it starts being loaded.
- The infrastructure specialist's run fails before its first call: Gemini
  refuses a tool schema as having "too much branching". The same test fails
  the same way at `ea5575d`, before this change, so it comes from the
  `kubernetes` toolset's schemas rather than from guides. Out of scope here.
- The metrics guide does not cover the grammar in `METRIC_QUERY_DIALECT`. It
  teaches the shape (`avg:metric{scope}`, a comma as AND, `p95:`) but not the
  rule each paragraph was written for: that `,` and `!` must not share braces
  with `AND`, `OR`, `NOT` or `IN`. Nor `!` or `.as_count()`. So task 5.3's
  condition is not met and the grammar stays.
