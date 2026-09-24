## Why

Every specialist can reach `list_datadog_skills` and `load_datadog_skill`, so it
can browse the platform's whole library of guides — including guides for tools
its declaration does not permit. The model then reads about a tool it cannot
call, and sometimes tries to.

Browsing also costs more than it looks. The two skill tools are declared like
any other, so every list or load counts against the specialist's
`max_tool_calls_per_agent`, is kept as citable evidence under a `call-N`, and,
if it fails, marks the investigation incomplete.

The guides themselves are worth keeping: the metrics guide carries the full
query grammar, and query syntax is the first failure `docs/vision.md` names
under "A Datadog integration that holds up".

## What Changes

- **Guides are loaded once per run, not browsed by the model.** Before the first
  investigation of a run, the platform's guides are listed and loaded.
- **Each specialist is given the guides that concern its own tools.** A guide is
  given to a specialist when it names at least one tool that specialist's
  declaration permits. No list of guide names is maintained by hand: the tool
  list each declaration already holds is what decides.
- **The guides are part of the specialist's instruction** rather than something
  it must remember to fetch.
- **BREAKING (internal): specialists no longer reach the two skill tools.**
  `CONSULT_THE_PLATFORM` is replaced by a short line saying a guide may mention
  tools the specialist does not have, and that only its own are callable.
- **A run whose guides cannot be loaded still runs**, without them, and says so
  in the log.
- **The grammar half of `METRIC_QUERY_DIALECT` is retired** once a live run
  shows the metrics guide covers it. Its judgement half stays: a refused
  aggregation is not a healthy service. `AN_EMPTY_ANSWER` stays whole, because
  it is this project's reasoning about evidence, not the platform's grammar.

Out of scope: refreshing guides inside a run (a run is one process and short),
and guides from providers other than Datadog.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `investigation`: gains one requirement — a specialist is given the platform's
  guidance for the tools it may reach, and no guidance chosen by the model at
  runtime. The existing "declaration owns what it may ask" requirement is
  unchanged; this narrows it further.

## Impact

- `investigation/adapters/datadog/`: the skill tool names, the matching rule,
  and the retired dialect text.
- `investigation/adapters/adk/`: fetching the guides over MCP, and composing
  them into an agent's instruction.
- `investigation/adapters/crew/specialists/*`: the skill tools leave every
  toolset; `CONSULT_THE_PLATFORM` leaves every instruction.
- `app/composition.py`: unchanged in shape — the investigator it builds now
  loads guides on its first investigation.
- Tests: the unit test that every specialist *can* consult the platform's
  guidance inverts; the live platform suite gains a check that each specialist
  is matched to at least one guide.
- No new runtime dependency: ADK's MCP toolset already reaches the server.
