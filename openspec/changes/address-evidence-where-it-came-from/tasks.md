Each task is one red / green / refactor cycle. The test named in a task is
written first and watched fail before the code that satisfies it exists.
Test files are named for the behaviour they establish and live at the mirror
of the module's own path, per AGENTS.md.

Tasks 1 to 3 are the gate: after them, no retrieval is addressed as a page it
did not come from. Tasks 4 and 5 are additive, one form at a time, and a form
that fails its live check is dropped rather than shipped.

## 1. A retrieval is addressed as what produced it

- [x] 1.1 In `tests/unit/investigation/adapters/datadog/test_evidence_is_addressed_where_it_lives.py`,
  assert a retrieval from a tool `DatadogLinks` has no address form for gets
  no address at all — `None`, not a Log Explorer search. Give
  `DatadogLinks.to_retrieval` the tool's name and route on it, with the
  existing Log Explorer construction reached only by the log tools.
- [x] 1.2 In the same file, assert the log tools still produce exactly the
  address they produce today, query and window and `live=false` included. This
  is the refactor's safety net: the one form already confirmed against a real
  account must come out the other side unchanged.
- [x] 1.3 Assert `to_item` routes the same way, so an item from an unmapped
  tool inherits nothing rather than inheriting a log address. Give it the tool
  name too, and keep the fallback-to-the-retrieval behaviour within a form.

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
  address form or is recorded as deliberately having none. Watch it fail for
  the tools with no form yet, then add the record. This is what keeps a
  specialist widened later from losing its addresses quietly.

## 4. A form per tool, each confirmed

Each of these is one cycle: a unit test asserting the string, then the live
check asserting it answers. A form whose live check fails is removed and its
tools left linkless, which task 1 made a correct outcome. Every form is
composed from the service and the window the investigation already holds — no
form reads a query out of the retrieval's `args`, for the reasons in
design.md.

- [ ] 4.1 The APM tools — `get_datadog_metric`, `search_datadog_metrics`,
  `get_datadog_metric_context` and the catalogue tool — addressed as the
  service's own page:
  `https://{host}/apm/entity/service%3A{service}?start={ms}&end={ms}`.
- [ ] 4.2 The span and trace tools — `search_datadog_spans`,
  `get_datadog_trace` — addressed as the trace explorer scoped to the service:
  `https://{host}/apm/traces?query=service%3A{service}&start={ms}&end={ms}`.
- [ ] 4.3 The host and Kubernetes tools — `search_datadog_hosts`,
  `search_datadog_k8s_resources`, `describe_datadog_k8s_resource`.
- [ ] 4.4 `search_datadog_events`, which has a form already written next door in
  `triage/adapters/datadog/alert_source.py` and confirmed live. Written again
  here rather than shared — see design.md.
- [ ] 4.5 Assert in each cycle that the window is expressed in milliseconds
  under the parameter names that form uses — `start`/`end` for the APM forms,
  `from_ts`/`to_ts` for the log one — and that a form whose window cannot be
  read drops both ends rather than one, which `links._window` already does.

## 5. A finding says which section it concerns

- [ ] 5.1 In `tests/unit/investigation/test_findings.py`, assert `Finding`
  carries an optional section drawn from an enumerated set and defaults to
  none, so every existing construction keeps compiling. Add it to
  `investigation/contract.py` alongside the set it is drawn from.
- [ ] 5.2 In the specialist schema tests, assert a specialist may set it and
  that a value outside the set does not validate — the bound is what makes this
  admissible at all. Watch the rejection fail first.
- [ ] 5.3 In `tests/unit/triage/domain/test_what_a_report_says.py`, assert a
  finding with a section renders a service-page address anchored to it, that a
  finding with none renders the same address without an anchor, and that an
  unrecognised section is treated as none rather than concatenated. Compose the
  address where the report is built, from the service, the window and the
  section.
- [ ] 5.4 Assert the evidence's own retrieval address is unchanged and still
  rendered beside it. Two addresses, two jobs: where this evidence came from,
  and where to go and look at the service.

## 6. The live check covers the crew, not one specialist

- [x] 6.1 In `tests/integration/investigation/adapters/datadog/test_every_specialist_reaches_the_real_platform.py`,
  parameterise the address check over `CREW` rather than running it against
  `LOGS_SPECIALIST` alone, the way the declaration check beside it already is.
  Assert each specialist's `call-1` either opens or is absent by design — both
  are specified outcomes, and a Log Explorer address for a metric retrieval is
  neither.
- [ ] 6.2 Assert an anchored service-page address opens, and that it opens for
  an anchor the enumerated set contains. The section is the one part of an
  address this project lets the reasoning choose, so it is the part worth
  seeing resolve against a real account.
- [ ] 6.3 Run `uv run --env-file .env pytest
  tests/integration/investigation/adapters/datadog -rs` and record the outcome
  here: which forms were confirmed to open, which specialists ship linkless,
  and which forms were written and then dropped. Credential-gated, so a
  developer's run and not CI's — see
  [`docs/live-testing.md`](../../../docs/live-testing.md).
- [ ] 6.4 Say plainly in that record that `to_item` was not exercised live.
  Per-item citations do not resolve against the real server while the MCP
  envelope stays unwrapped, so every live address is a retrieval address and
  the item forms are unit-tested only.

## 7. Close the change

- [ ] 7.1 Run the full gate: `uv run ruff check src tests`,
  `uv run ruff format --check src tests`, `uv run mypy`, `uv run pytest`.
- [ ] 7.2 `openspec validate address-evidence-where-it-came-from --strict`.
- [x] 7.3 Update `links.py`'s module docstring, which currently describes every
  address as a Log Explorer search. It is the file's own account of what it
  does and it stops being true in task 1.
