## 1. The move, changing nothing

Behaviour-preserving, `git mv` throughout, its own commit. No test is rewritten
here — only import paths and file locations move. The suite passing unchanged is
the whole verification this group gets, and is what it is entitled to.

- [x] 1.1 `git mv` the four declarations from
  `investigation/adapters/datadog/specialists/{logs,apm,trace,infrastructure}.py`
  to `investigation/adapters/crew/specialists/`, with `__init__.py`.
- [x] 1.2 `git mv` `investigation/adapters/datadog/specialists/{dialect,preview}.py`
  to `investigation/adapters/datadog/` — the platform's grammar and its
  account's toolset availability are plumbing, not declarations — and drop the
  now-empty `datadog/specialists/`.
- [x] 1.3 `git mv` `investigation/adapters/adk/reasoners/` to
  `investigation/adapters/crew/reasoners/`.
- [x] 1.4 `git mv` `investigation/adapters/adk/crew.py` to
  `investigation/adapters/crew/roster.py`; which specialists exist is not a
  framework fact.
- [x] 1.5 Update every import of the moved modules (`adk/agent.py`,
  `adk/investigator.py`, `app/composition.py`, the declarations themselves) and
  the module docstrings that name the old locations.
- [x] 1.6 `git mv` the mirroring tests: `tests/unit/investigation/adapters/adk/reasoners/`
  and `test_crew.py` → `tests/unit/investigation/adapters/crew/`; the four
  `datadog/test_*_specialist*.py`, `test_a_declaration_and_its_instruction_agree.py`
  and `test_every_specialist_can_consult_the_platforms_guidance.py` →
  `tests/unit/investigation/adapters/crew/`; leave `test_mcp.py`,
  `test_evidence_is_addressable.py` and `test_the_metric_dialect_is_taught_once.py`
  under `datadog/`.
- [x] 1.7 Run all four CI commands; every test passes with no test body changed.
  Commit the move on its own.

## 2. A toolset names its provider

- [x] 2.1 Red: in `tests/unit/investigation/domain/test_a_specialist_is_declared_whole.py`,
  assert a `Toolset` declared without a provider is refused. Watch it fail.
- [x] 2.2 Green: add `provider: str` to `Toolset` with the `__post_init__`
  rejection beside its siblings.
- [x] 2.3 Export the Datadog provider constant from
  `investigation/adapters/datadog/mcp.py` and name it on every toolset in the
  four declarations. Test that no declaration names a provider by literal.
- [x] 2.4 Run the four CI commands.

## 3. A deployment maps providers to where they are

- [ ] 3.1 Red: in `tests/unit/investigation/adapters/adk/test_an_agent_is_built_from_a_declaration.py`,
  assert `connection_for` composes a toolset's URL from *its own* provider's
  access, given a deployment holding two. Watch it fail.
- [ ] 3.2 Green: add `PlatformAccess` (endpoint + headers); replace
  `Deployment.endpoint`/`.headers` with `platforms: Mapping[str, PlatformAccess]`;
  have `connection_for` look up `toolset.provider`.
- [ ] 3.3 Red then green: `connection_for` on a provider the deployment does not
  hold raises, naming the provider and what the deployment holds.
- [ ] 3.4 Red then green: one specialist declaring toolsets on two providers
  reaches both, each through its own endpoint and headers — the spec's *A
  specialist draws on two providers* scenario, against two fake MCP servers in
  `tests/integration/investigation/adapters/adk/`.
- [ ] 3.5 Update `app/composition.py` to build `platforms={DATADOG: PlatformAccess(...)}`,
  and every test that constructs a `Deployment`.
- [ ] 3.6 Run the four CI commands.

## 4. A deployment offers the specialists it can reach

- [ ] 4.1 Red: in `tests/unit/investigation/adapters/crew/test_crew.py`, assert
  a specialist whose provider the deployment did not configure is not in the
  roster. Watch it fail.
- [ ] 4.2 Green: `crew_for` takes the configured provider names alongside the
  per-specialist model overrides, and filters to specialists whose every toolset
  names one of them.
- [ ] 4.3 Red then green: a specialist naming two providers where only one is
  configured is not offered — half its evidence is not a specialist.
- [ ] 4.4 Red then green: an empty crew raises `ConfigError` at composition,
  naming what is missing, before any alert is fetched.
- [ ] 4.5 Red then green: with every provider configured, the roster is exactly
  what it is today — the existing crew tests hold unchanged.
- [ ] 4.6 Wire the provider names through `app/composition.py` from the same
  `Deployment` it just built, so the two cannot disagree.
- [ ] 4.7 Run the four CI commands.

## 5. What the docs say

- [ ] 5.1 `docs/adapters.md`: a declaration lives with the crew, not under a
  platform; `toolsets` carries the provider serving each group; what a
  deployment must configure for a specialist to be offered; the two-provider
  case.
- [ ] 5.2 `AGENTS.md`: reword the `investigation/` bullet — its adapters split
  into `crew/`, `adk/` and `datadog/`, and what each holds.
- [ ] 5.3 `README.md` where it names the tree. The architecture diagram is
  slice 15's and is not redrawn here.
- [ ] 5.4 `docs/vision.md`: mark slice 10 done and record the answer taken on
  which crew a deployment runs (proposal.md — Assumption).

## 6. Before calling it done

- [ ] 6.1 `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy`, `uv run pytest` — all four green.
- [ ] 6.2 Run the credential-gated live tests
  (`docs/live-testing.md`) — this change touches composed URLs and connection
  parameters, which a green local run does not establish. State plainly whether
  they were run.
- [ ] 6.3 `openspec validate specialist-belongs-to-its-signal`, then
  `/opsx:archive`.
