Each task is one red / green / refactor cycle. The test named in a task is
written first and watched fail before the code that satisfies it exists. Test
files are named for the behaviour they establish and live at the mirror of the
module's own path, per AGENTS.md.

## 1. Scope resolves an environment

- [ ] 1.1 In `tests/unit/configuration/`, assert `Scope()` watches `prod` when
  nothing names an environment. Add `env: str = "prod"` to `Scope`.
- [ ] 1.2 In `tests/integration/configuration/test_yaml_config_loader.py`,
  assert `scope.env` resolves from the file, from `SCOPE_ENV`, with the
  environment winning, and defaults to `prod` when neither sets it. Read it in
  `_scope` through `_supplied`, and let `_reject_unknown` accept the new key.
- [ ] 1.3 Assert a scope with only `env` still refuses to start with the
  existing "requires an owner, services, or both" message.
- [ ] 1.4 Assert an empty or blank `scope.env` / `SCOPE_ENV` is refused by name.

## 2. Only the environment's alerts are fetched

- [ ] 2.1 In `tests/unit/triage/adapters/datadog/test_alert_source.py`, assert
  the search query carries `env:<name>` beside the owner and service terms.
  Give `DatadogAlertSource` and `build_alert_source` an `env` argument and
  spend it in `_query`.
- [ ] 2.2 Assert a failed fetch names the environment in its message, via
  `_scope`.
- [ ] 2.3 Assert the Event Explorer fallback link's query carries `env:<name>`,
  and a monitor link is unchanged.
- [ ] 2.4 Pass `config.scope.env` into `build_alert_source` in
  `app/composition.py`, covered by the composition test that already checks
  owner and services are handed over.

## 3. An investigation is told the environment

- [ ] 3.1 In `tests/unit/investigation/test_investigation_target.py`, assert
  a target built with `env="prod"` states it in `describe()`, and one built
  without states that no environment was given. Add
  `env: str | None = None` to `InvestigationTarget`.
- [ ] 3.2 In the incident's unit tests under `tests/unit/triage/domain/`,
  assert `investigation_target(scope)` carries `scope.env`.
- [ ] 3.3 Change the scoping sentence in
  `investigation/adapters/datadog/dialect.py` to service *and* environment, and
  the matching lines in the logs, APM, trace and infrastructure specialists'
  instructions. Assert it in whichever unit test already pins the dialect's
  wording; if none does, add one that asserts the instruction names the
  environment.

## 4. Composed addresses stay inside the environment

- [ ] 4.1 Assert the Log Explorer address is still built from the query as it
  ran, with no environment added, in the existing links tests.
- [ ] 4.2 Conditional on `address-evidence-where-it-came-from` having landed:
  assert the APM service-page form carries `env=<name>` and the trace explorer
  form carries `env:<name>` in its query when the target states one, and
  neither when it does not. If that change has not landed, add this
  requirement to its tasks instead and leave this box unticked with a note.

## 5. A report names the environment

- [ ] 5.1 In the report's unit tests under `tests/unit/triage/domain/`, assert
  both the pass-through and the investigated report carry the environment
  after the subject prefix and in the body's first sentence. Give the report
  builder an `env` argument.
- [ ] 5.2 Pass `scope.env` into the report builder from `app/pipeline.py`.

## 6. Documentation

- [ ] 6.1 Add `env` to `scope` in `config.example.yaml`, and extend the test
  that loads the example so it still resolves.
- [ ] 6.2 In `docs/configuration.md`, name `scope.env` / `SCOPE_ENV`, its
  `prod` default, that it narrows but never satisfies scope, and that changing
  it on a running deployment means a fresh ledger.
- [ ] 6.3 Add `scope.env` to the `scope` bullet list in `docs/vision.md`'s
  configuration section.

## 7. Before calling it done

- [ ] 7.1 Run `uv run ruff check src tests`, `uv run ruff format --check src
  tests`, `uv run mypy` and `uv run pytest`; all four pass.
- [ ] 7.2 Say plainly in the PR that the specialists' instructions changed and
  the credential-gated live tests (`docs/live-testing.md`) were not run.
