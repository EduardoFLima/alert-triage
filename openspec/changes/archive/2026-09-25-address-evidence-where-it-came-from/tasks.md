Each task is one red / green / refactor cycle. The test named in a task is
written first and watched fail before the code that satisfies it exists.
Test files are named for the behaviour they establish and live at the mirror
of the module's own path, per AGENTS.md.

Tasks 1 to 3 are the gate: after them, no retrieval is addressed as a page it
did not come from. Tasks 4 and 5 are additive, one template at a time, and a
template that fails its live check is dropped rather than shipped.

## 1. A retrieval is addressed as what produced it

- [x] 1.1 In `tests/unit/investigation/adapters/datadog/test_evidence_is_addressed_where_it_lives.py`,
  assert a retrieval from a tool `DatadogLinks` has no address template for
  gets no address at all — `None`, not a Log Explorer search. Give
  `DatadogLinks.to_retrieval` the tool's name and route on it, with the
  existing Log Explorer construction reached only by the log tools.
- [x] 1.2 In the same file, assert the log tools still produce exactly the
  address they produce today, query and window and `live=false` included. This
  is the refactor's safety net: the one template already confirmed against a
  real account must come out the other side unchanged.
- [x] 1.3 Assert `to_item` routes the same way, so an item from an unmapped
  tool inherits nothing rather than inheriting a log address. Give it the tool
  name too, and keep the fallback-to-the-retrieval behaviour within a template.

## 2. The framework hands the platform the tool

- [x] 2.1 In `tests/unit/investigation/adapters/adk/test_only_what_was_retrieved_is_citable.py`,
  assert `retain_evidence` passes the tool it was called for to the linker, and
  that a `Retrieved` built without a linker still keeps every `url` at `None`.
  Add the tool's name to `Links.to_retrieval` and `Links.to_item` in
  `adk/evidence.py`, and thread it through `_address_of` and `_item_addresses`.
- [x] 2.2 In `tests/unit/investigation/adapters/adk/test_a_tool_result_reaches_the_model_checked.py`,
  assert `_kept` hands `retain_evidence` the name it already computed for the
  permitted-tools check rather than computing it twice or passing the tool
  object. A failed retrieval is still refused unchanged.
- [x] 2.3 Run `uv run pytest tests/unit/investigation/adapters/adk/test_architecture.py`
  — or the architecture test wherever it lives — and confirm `adk/` still has
  no import of `datadog/`. The tool name is a string; if this cycle needed an
  import, the linker has stopped being injected.

## 3. No tool is forgotten

- [x] 3.1 In `tests/unit/investigation/adapters/datadog/test_evidence_is_addressed_where_it_lives.py`,
  assert that for every tool the crew declares, `DatadogLinks` either has an
  address template or is recorded as deliberately having none. Watch it fail
  for the tools with no template yet, then add the record. This is what keeps a
  specialist widened later from losing its addresses quietly.

## 4. A template per tool, each confirmed

Each of these is one cycle: a unit test asserting the string, then the live
check asserting it answers. A template whose live check fails is removed and
its tools left linkless, which task 1 made a correct outcome. Every template is
composed from the service and the window the investigation already holds — no
template reads a query out of the retrieval's `args`, for the reasons in
design.md.

- [x] 4.1 The APM tools — `get_datadog_metric`, `search_datadog_metrics`,
  `get_datadog_metric_context` and the catalogue tool — addressed as the
  service's own page:
  `https://{host}/apm/entity/service%3A{service}?start={ms}&end={ms}`.
- [x] 4.2 The span and trace tools — `search_datadog_spans`,
  `get_datadog_trace` — addressed as the trace explorer scoped to the service:
  `https://{host}/apm/traces?query=service%3A{service}&start={ms}&end={ms}`.
- [x] 4.3 The host and Kubernetes tools — `search_datadog_hosts`,
  `search_datadog_k8s_resources`, `describe_datadog_k8s_resource`.
- [x] 4.4 `search_datadog_events`, which has a template already written next
  door in `triage/adapters/datadog/alert_source.py` and confirmed live. Written
  again here rather than shared — see design.md.
- [x] 4.5 Assert in each cycle that the window is expressed in milliseconds
  under the parameter names that template uses — `start`/`end` for the APM
  templates, `from_ts`/`to_ts` for the log one — and that a template whose
  window cannot be read drops both ends rather than one, which `links._window`
  already does.

## 5. A finding says which section it concerns

- [x] 5.1 In `tests/unit/investigation/test_findings.py`, assert `Finding`
  carries an optional section drawn from an enumerated set and defaults to
  none, so every existing construction keeps compiling. Add it to
  `investigation/contract.py` alongside the set it is drawn from.
- [x] 5.2 In the specialist schema tests, assert a specialist may set it and
  that a value outside the set does not validate — the bound is what makes this
  admissible at all. Watch the rejection fail first.
- [x] 5.3 In `tests/unit/triage/domain/test_what_a_report_says.py`, assert a
  finding with a section renders a service-page address anchored to it, that a
  finding with none renders the same address without an anchor, and that an
  unrecognised section is treated as none rather than concatenated. Compose the
  address where the report is built, from the service, the window and the
  section.
  Done where the account is rendered rather than in
  `triage/domain/report.py`, which reads a diagnosis' headline and account and
  no longer sees a finding: `investigation/domain/account.py` renders the
  address from a page callable the investigator hands it, and `DatadogLinks`
  composes it, so no Datadog route enters a domain layer. The tests live in
  `tests/unit/investigation/domain/test_a_finding_points_at_the_service_it_concerns.py`.
- [x] 5.4 Assert the evidence's own retrieval address is unchanged and still
  rendered beside it. Two addresses, two jobs: where this evidence came from,
  and where to go and look at the service.

## 6. The live check covers the crew, not one specialist

- [x] 6.1 In `tests/integration/investigation/adapters/datadog/test_every_specialist_reaches_the_real_platform.py`,
  parameterise the address check over `CREW` rather than running it against
  `LOGS_SPECIALIST` alone, the way the declaration check beside it already is.
  Assert each specialist's `call-1` either opens or is absent by design — both
  are specified outcomes, and a Log Explorer address for a metric retrieval is
  neither.
- [x] 6.2 Assert an anchored service-page address opens, and that it opens for
  an anchor the enumerated set contains. The section is the one part of an
  address this project lets the reasoning choose, so it is the part worth
  seeing resolve against a real account. Pass the target's service into the
  `Retrieved`/`_Recorded` the live run builds: task 4 threaded the service
  through the linker but left the live wrapper constructing `Retrieved()`
  service-less, so every service-scoped address resolves against an empty
  `service:` until this does.
- [x] 6.3 Run `uv run --env-file .env pytest
  tests/integration/investigation/adapters/datadog -rs` and record the outcome
  here: which templates were confirmed to open, which specialists ship
  linkless, and which templates were written and then dropped.
  Credential-gated, so a developer's run and not CI's — see
  [`docs/live-testing.md`](../../../docs/live-testing.md). Watch the
  infrastructure template (task 4.3) first: it is the one written without a
  shape given in its task — `…/infrastructure?filter=service:{service}`, and
  windowless because the inventory is a live view — so it is the likeliest of
  the four to be confirmed-or-dropped here.

  **The record.** Run against an account on `datadoghq.eu`, with
  `ALERT_TRIAGE_LIVE_SERVICE` set to `msam.planning.sam-activity-service` — a
  service that exists and is busy. An earlier run against the default
  `checkout` is not reported here: no such service exists in this account, and
  a template cannot be said to have been confirmed against nothing. Result: 18
  passed, 3 failed, 1 skipped, in 4m54s.

  *Every template was confirmed to open. None was dropped.* The five are the
  Log Explorer search, the APM service page, the Trace Explorer scoped to the
  service, the infrastructure inventory, and the Event Explorer. The
  infrastructure template the task told us to watch is among them: it answers
  as written, windowless, and survives.

  The log template earned a second, better confirmation than a status code.
  Datadog's own answer to `search_datadog_logs` carries a `logs_explorer_url`
  it composed itself, and the address this project composed for the same
  retrieval agrees with it on query, on both ends of the window as millisecond
  timestamps, and on `live=false`. Task 4.5 asserted that shape against a unit
  test; the platform has now written it back to us unprompted.

  Three of the four specialists established their addresses through
  `test_each_retrieval_address_opens_rather_than_404s_or_is_absent` — logs, APM
  and trace each retrieved, and every retrieval either opened or was `None` for
  a tool in `UNADDRESSED`. The fourth could not: the
  `infrastructure_specialist` never reaches the platform at all, because the
  model refuses its tool schema before any call is made —
  `400 INVALID_ARGUMENT … the specified schema produces a constraint that has
  too much branching for serving`. That is the Kubernetes tools' own schemas,
  and it fails the older
  `test_a_real_model_given_the_instruction_calls_them[infrastructure_specialist]`
  identically, so it predates this change and is not about addressing. Its
  template was therefore confirmed by following the composed address directly
  against the account rather than through a specialist that cannot run — the
  same question the `answers` check asks, minus the model. That it opens is
  established; that *this specialist* emits it is not, and stays unestablished
  until the schema problem is taken on as its own change.

  The anchored service page opens for all six sections and for none, which is
  task 6.2 confirmed live rather than asserted. What that cannot establish
  stands as written in the test: a browser resolves the fragment and the server
  never sees one.

  *Linkless.* No specialist ships wholly linkless. What ships linkless is the
  tools in `UNADDRESSED`: the two skill tools every specialist reaches, whose
  results are the platform's guidance on its own grammar rather than evidence,
  plus the Watchdog, change-story, rollout-analysis, latency-bottleneck,
  trace-query and span-tag tools. The run confirmed these are addressed as
  `None` rather than inheriting a neighbour's page, which is task 1's gate
  holding under a real model's tool choices.

  *The third failure was not about addressing, and was not the bound doing its
  job either.* The APM specialist stopped after 12 calls while this deployment
  is configured for 30. `build_agent` took its bounds as a separate argument
  and fell back to the documented defaults when given none, so an agent built
  straight from a deployment ignored that deployment's own breakers — which is
  exactly what the live suite's `_deployment` docstring says must not happen.
  Fixed under its own commit, with the unit tests that were missing; recorded
  here because the run is only honest whole, and because a default is a
  plausible enough number to have gone unquestioned.
- [x] 6.4 Say plainly in that record that `to_item` was not exercised live.
  Per-item citations do not resolve against the real server while the MCP
  envelope stays unwrapped, so every live address is a retrieval address and
  the item templates are unit-tested only.

  **Said plainly: `to_item` was not exercised live, and the reason is worse
  than the one this task anticipated.** Every address followed above is a
  retrieval address. The item templates are unit-tested only.

  The task assumed the obstacle was an MCP envelope left unwrapped. Against a
  real account it is not an envelope at all. `search_datadog_logs` does not
  answer with JSON: it answers with a block of text holding a `<METADATA>`
  header and a `<TSV_DATA>` table. `readable()` hands that back as a `str`,
  `_items()` reads items only out of a list or a list under one of
  `ENVELOPE_KEYS`, and a string is neither — so the retrieval yields **zero
  items**, no `call-N/item-M` is ever minted, and `to_item` is never called.
  Widening `ENVELOPE_KEYS` would not reach it; there is no key.

  This was masked. The live item test skips with *the logs of … were quiet, so
  no item was returned*, and that reading is wrong: the logs were not quiet.
  The retrieval came back with two patterns covering 60 error-level lines,
  including a `RollingFileAppender … RolloverFailure` recurring 58 times. The
  test infers a quiet service from an absence of items, and the absence has a
  different cause. So the design's open question — which of `ITEM_KEYS` a live
  payload uses — is not merely still open; it cannot be answered by this test
  while the payload is TSV, whatever service it is pointed at.

  None of this weakens the change. A retrieval with no items is citable whole,
  which is the degradation `normalisation` was built for, and its retrieval
  address opens. But two follow-ups are owed, and neither belongs here:
  reading Datadog's `METADATA`/`TSV_DATA` answers into items, and a skip
  message that says what was actually absent.

## 7. Close the change

- [x] 7.1 Run the full gate: `uv run ruff check src tests`,
  `uv run ruff format --check src tests`, `uv run mypy`, `uv run pytest`.
- [x] 7.2 `openspec validate address-evidence-where-it-came-from --strict`.
- [x] 7.3 Update `links.py`'s module docstring, which currently describes every
  address as a Log Explorer search. It is the file's own account of what it
  does and it stops being true in task 1.
