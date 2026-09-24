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

- **The guides are fetched from Datadog once, at startup.** While the
  investigator is being assembled, the guides are listed and each is loaded,
  with the references it points to. They are held in memory for the run and
  never written anywhere.
- **Each specialist is offered the guides that concern its own tools.** A guide
  concerns a specialist when it names at least one tool that specialist's
  declaration permits. No list of guide names is kept by hand: the tool list
  each declaration already holds decides.
- **ADK's `SkillToolset` serves them.** Each specialist gets one holding only
  its matched guides. ADK puts a menu of their names and descriptions in the
  prompt, and the specialist loads a guide's text when it needs it. A name not
  on its menu is refused, because the toolset does not hold it.
- **Loading a guide is not a retrieval.** It reaches no server, so it uses no
  tool budget, is not evidence, and cannot mark an investigation incomplete.
- **BREAKING (internal): specialists lose both Datadog skill tools.**
  `CONSULT_THE_PLATFORM` leaves every instruction; the menu replaces it.
- **A run whose guides cannot be fetched still runs**, with no guides offered,
  and says so in the log.
- **The grammar half of `METRIC_QUERY_DIALECT` is retired** once a live run
  shows the metrics guide covers it. Its judgement half stays: a refused
  aggregation is not a healthy service. `AN_EMPTY_ANSWER` stays whole, because
  it is this project's reasoning about evidence, not the platform's grammar.

Out of scope:

- Keeping guides between runs, on disk or in the repo.
- Changing the generic instruction ADK adds alongside the menu.
- Guides from providers other than Datadog.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `investigation`: gains one requirement — a specialist is offered the
  platform's guidance for the tools it may reach, loads it on demand, can load
  nothing else, and loading is not a retrieval. The existing "declaration owns what it may ask" requirement is
  unchanged; this narrows it further.

## Impact

- `investigation/adapters/datadog/`: the skill tool names, turning a Datadog
  guide into a name ADK accepts, and the matching rule.
- `investigation/adapters/adk/`: fetching the guides over MCP, building ADK
  `Skill` objects, and giving each agent its `SkillToolset`.
- `investigation/adapters/crew/specialists/*`: both skill tools leave every
  toolset; `CONSULT_THE_PLATFORM` leaves every instruction.
- `app/composition.py`: `build_investigator` fetches the guides once and hands
  them to the deployment.
- Tests: the unit test that every specialist *can* consult the platform's
  guidance inverts; the live platform suite gains a check that each specialist
  is offered at least one guide.
- No new runtime dependency: `SkillToolset` and the MCP toolset are both ADK's.
