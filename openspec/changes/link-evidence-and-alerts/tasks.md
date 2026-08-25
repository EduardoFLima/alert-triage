Each task is one red / green / refactor cycle. The test named in a task is
written first and watched fail before the code that satisfies it exists.
Test files are named for the behaviour they establish and live at the mirror
of the module's own path, per AGENTS.md.

## 1. Evidence gains an address

- [x] 1.1 In `tests/unit/investigation/test_findings.py`, assert an
  `EvidenceItem` carries a `url` and that it defaults to `None` when nothing
  supplies one. Add `url: str | None = None` to `EvidenceItem` in
  `investigation/contract.py`, and extend its docstring to say the address is
  derived from what was retrieved and absent where the platform offers none.
- [x] 1.2 In `tests/unit/investigation/adapters/adk/test_items_are_read_out_of_any_result.py`,
  assert `items_from` gives each item the address a supplied linker returns for
  its payload, and leaves `url` at `None` when no linker is supplied. Thread a
  `Linker` argument through `normalisation.items_from` and `_item`, declaring
  `Linker = Callable[[Any], str | None]` beside them.

## 2. What was retrieved carries where to find it

- [x] 2.1 In `tests/unit/investigation/adapters/adk/test_only_what_was_retrieved_is_citable.py`,
  assert a `Retrieved` built with a linker resolves items to evidence carrying
  the address, and one built without keeps every `url` at `None`. Give
  `Retrieved.__init__` a `link: Linker | None = None` and pass it into
  `items_from`.
- [x] 2.2 In the same file, assert the call-level `EvidenceItem` — the one an
  aggregate is cited by — carries the address built for the retrieval as a
  whole. Pass the tool arguments into `Retrieved.retain` alongside the result,
  and give the linker a second entry point for a retrieval rather than an item.
- [x] 2.3 In `tests/unit/investigation/adapters/adk/test_a_tool_result_reaches_the_model_checked.py`,
  assert `evidence_kept` hands the tool's `args` to `retain` rather than
  dropping them, and that a failed retrieval is still refused unchanged.
- [x] 2.4 Confirm the model is still never shown an address: assert `_offered`
  carries `id`, `instant`, `summary` and `data` and nothing URL-shaped, so a
  specialist has no address to copy into a finding.

## 3. Datadog's addresses

- [x] 3.1 Write `tests/unit/investigation/adapters/datadog/test_evidence_is_addressable.py`
  first: a log payload naming an entry yields that entry's address; a payload
  naming none yields the address of the retrieval it came from; an unreadable
  payload yields `None`. Then write
  `investigation/adapters/datadog/links.py` with a builder bound to a site.
- [x] 3.2 In the same file, assert a retrieval's address carries the query the
  tool was called with and the window it ran over, URL-encoded, so a reader
  lands on the search that produced the evidence.
- [x] 3.3 Assert the builder is bound to the deployment's site, so an account on
  `datadoghq.eu` never receives a `datadoghq.com` address.

## 4. An alert links somewhere that opens

- [x] 4.1 In `tests/unit/triage/adapters/datadog/test_alert_source.py`, assert a
  translated alert whose event carries a monitor id links to that monitor,
  scoped to when it fired — and that the link is no longer built from the v2
  event id. Replace the `/event/event?id=` construction in
  `triage/adapters/datadog/alert_source.py`.
- [x] 4.2 Assert an event carrying no monitor id falls back to an Event Explorer
  address over its service and window, and that an event from which neither can
  be built leaves `Alert.link` at its empty default rather than inventing one.

## 5. The report renders a link as a link

- [x] 5.1 In `tests/unit/triage/domain/test_what_a_report_says.py`, assert a
  finding whose evidence carries an address renders that address on its own
  line, below the evidence line, and that evidence without one renders exactly
  as it does today. Turn `report._evidence_line` into a small list and have
  `_finding_lines` extend it.
- [x] 5.2 Assert a long summary is still shortened while its address is rendered
  whole, which is the failure this change exists to fix.

## 6. Wiring

- [x] 6.1 In `tests/unit/app/test_composition.py`, assert the investigator is
  constructed with a linker bound to the configured Datadog site. Pass it
  through `AdkInvestigator` to the `Retrieved` it builds per investigation.
- [x] 6.2 Run `uv run pytest tests/unit` and confirm `test_architecture.py`
  still passes — `adk/` must not have gained an import of `datadog/` for the
  linker, which arrives injected.

## 7. Verify against the real platform

- [x] 7.1 In `tests/integration/triage/adapters/datadog/test_alert_source_live.py`,
  assert a built alert address answers rather than 404s. Credential-gated and
  skipped without them, like its neighbours.
- [x] 7.2 In `tests/integration/investigation/adapters/datadog/test_logs_specialist_live.py`,
  assert an address built from a real retrieval answers, and record in the test
  what key the live payload identifies an entry by — the design's open question.
- [ ] 7.3 Run the live checks against an account and note the outcome in the
  change before archiving. A URL form that fails here is the one thing no fake
  establishes.

  **Not yet run.** The checks are written and skip cleanly without credentials;
  the environment this change was implemented in has no Datadog or model key,
  so nothing has followed a built URL against a real account. Both URL forms
  the change ships — `/monitors/{id}` and the Log Explorer search — are
  therefore still established only as strings a unit test composed, which is
  exactly the standing this change exists to raise. Run
  `uv run pytest tests/integration/triage/adapters/datadog
  tests/integration/investigation/adapters/datadog` with
  `DD_API_KEY`, `DD_APP_KEY` and `GOOGLE_API_KEY` set, and record here what
  answered and which key a live log payload identifies an entry by — the
  second test prints it.

## 8. Close the change

- [x] 8.1 Run the full gate: `uv run ruff check src tests`,
  `uv run ruff format --check src tests`, `uv run mypy`, `uv run pytest`.
- [x] 8.2 Update `README.md` only if a report's shape is shown there. It is
  not — neither the README nor `docs/vision.md` renders a report body — so
  nothing there needed changing.
