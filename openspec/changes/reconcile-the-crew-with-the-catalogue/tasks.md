Each task is one red / green / refactor cycle. The test named in a task is
written first and watched fail before the code that satisfies it exists.
Test files are named for the behaviour they establish and live at the mirror
of the module's own path, per AGENTS.md.

## 1. Learn whether this is a correction or a repair

- [ ] 1.1 Run the live declaration check as it stands, before changing
  anything: `uv run --env-file .env pytest
  tests/integration/investigation/adapters/datadog -rs -k exists`. If
  `search_datadog_service_dependencies` still resolves, this change is a
  correction made ahead of time; if it does not, live runs are already failing
  and it is a repair. Record which, here, because it decides nothing about the
  work and everything about its urgency.

## 2. The APM specialist reaches the catalogue

- [ ] 2.1 In `tests/unit/investigation/adapters/crew/test_what_the_apm_specialist_looks_for.py`,
  assert the permitted tools contain `search_datadog_entities` and that no
  declaration permits or names `search_datadog_service_dependencies` — both
  branches, with and without Preview. Rename `DEPENDENCIES_TOOL` to
  `CATALOG_TOOL` in `specialists/apm.py` and change what it holds.
- [ ] 2.2 In the same file, assert the instruction tells the specialist what to
  *ask* the catalogue for rather than what the tool returns — the immediate
  upstream and downstream of the service it was given. Rewrite that line in
  `_CORE_TOOLS_DESCRIBED`. The existing assertions on "neighbour" and "one hop"
  must still pass unchanged; if either needs editing, the one-hop rule has been
  moved when it should not have been.
- [ ] 2.3 Assert the instruction's example of something cited as an aggregate no
  longer names a dependency map, whose grain the catalogue answer may not
  share. Reword it to an example that holds either way.

## 3. An empty answer is a rule stated once

- [ ] 3.1 In `tests/unit/investigation/adapters/crew/test_a_declaration_and_its_instruction_agree.py`,
  assert every specialist that queries anything carries the same wording for
  "an empty answer means it is not reported, which is not the same as healthy"
  — the shape `test_every_specialist_can_consult_the_platforms_guidance.py`
  already uses for `CONSULT_THE_PLATFORM`. Extract that principle into a
  constant in `adapters/datadog/dialect.py` and have all three instructions
  interpolate it. The per-signal mechanics — which listing tool to ask — stay
  in each specialist.

## 4. The trace specialist stops guessing a facet

- [ ] 4.1 In `tests/unit/investigation/adapters/crew/test_what_the_trace_specialist_looks_for.py`,
  assert the instruction carries the shared principle from 3.1 and says in as
  many words that an empty span search may be about the query rather than about
  the service. Add it to `_INSTRUCTION_TEMPLATE` in `specialists/trace.py`, in
  both the Preview and non-Preview forms.
- [ ] 4.2 In the same file, assert the Preview branch permits and names
  `apm_discover_span_tags` and that the non-Preview branch does neither —
  the gate the existing Preview tests already assert for `apm_query_trace`.
  Add it to the `apm` toolset and describe it in `_RANKING_TOOL_DESCRIBED`'s
  neighbourhood.

## 5. The infrastructure specialist can account for a rollout

- [ ] 5.1 In `tests/unit/investigation/adapters/crew/test_what_the_infrastructure_specialist_looks_for.py`,
  assert `analyse_datadog_k8s_rollout` is permitted on the `kubernetes`
  toolset and named in the instruction. Add it to
  `specialists/infrastructure.py`. Mind the spelling: this one is `analyse`
  where its catalogue neighbours are `analyze`.
- [ ] 5.2 In the same file, assert the instruction states the order — a
  workload is searched for before its rollout is analysed — and that what the
  specialist is asked to report includes the rollout alongside the restarts,
  without naming it as a cause. The existing "an empty answer is the
  deployment telling you it has no workload" assertions must still pass.

## 6. The vision stops naming a retired tool

- [ ] 6.1 Update the two mentions of `search_datadog_service_dependencies` in
  `docs/vision.md` — under the crew's APM agent, and in the tool list under
  *Evidence and the platform boundary*. The Grafana argument beside the first
  one is about a service-dependency tool existing at all, which is unchanged;
  only the Datadog tool's name moves.

## 7. Confirm against the real platform

- [ ] 7.1 Run `uv run --env-file .env pytest
  tests/integration/investigation/adapters/datadog -rs` and confirm every
  declared toolset resolves and a real model given each instruction still
  retrieves. Credential-gated, so this is a developer's run and not CI's — see
  [`docs/live-testing.md`](../../../docs/live-testing.md).
- [ ] 7.2 Record the outcome here before archiving, naming what was *not*
  established: the Preview branch is unverifiable while
  `APM_TOOLSET_AVAILABLE` is off, so `apm_discover_span_tags` ships declared
  and unconfirmed like the four Preview tools beside it. Say so plainly rather
  than letting a green run imply otherwise.
- [ ] 7.3 Note what the catalogue actually answered with, against the design's
  two open questions: whether entities come back as discrete items, and
  whether the search needed narrowing by environment to be useful. Both are
  observations from the run rather than assertions in a test.

## 8. Close the change

- [ ] 8.1 Run the full gate: `uv run ruff check src tests`,
  `uv run ruff format --check src tests`, `uv run mypy`, `uv run pytest`.
- [ ] 8.2 `openspec validate reconcile-the-crew-with-the-catalogue --strict`.
- [ ] 8.3 Nothing in `README.md` names a specialist's tools, so nothing there
  changes. Confirm rather than assume.
