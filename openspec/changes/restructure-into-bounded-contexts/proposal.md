## Why

`adapters/` groups modules by "this is an integration", which puts a 1046-line
agent subsystem beside a 60-line dotenv wrapper and leaves `datadog/` serving
two unrelated concerns. The next slices in `docs/vision.md` make this worse
before anything else does: slice 8's evaluation harness is a subsystem with no
home in the current tree, and slices 9–10 take investigation from one
specialist to six. Restructuring after they land means moving three times the
code.

The layering itself is sound and stays. What changes is the taxonomy inside
it: one global `domain`/`ports`/`adapters` triple becomes one hexagon per
bounded context.

## What Changes

- **Four contexts replace the flat layer folders.** `triage` (the Incident
  aggregate, grouping, triage policy), `investigation` (findings, evidence,
  the agent crew), `notification` (report delivery), and `configuration` (the
  YAML-backed behaviour settings). Each keeps its own `domain`/`ports`/
  `adapters` triple. The top-level `adapters/` package disappears.
- **Investigation gains a published contract and an anticorruption layer.**
  A new `InvestigationTarget` — service, window, alert count — replaces
  `Incident` at the port boundary, so investigation never learns what an
  incident is. This cuts the import cycle the context split would otherwise
  create.
- **Investigation's adapters split by axis**: `adk/` holds the agent framework,
  `datadog/` holds the platform — its MCP connection and its specialist
  declarations. This is what makes the contributor story in `docs/vision.md`
  a matter of adding one directory.
- **`Window` moves to a shared kernel** — one file, imported by two contexts,
  importing nothing itself.
- **The Datadog adapter splits along the two concerns it already serves.**
  Alert ingestion and credential resolution stay together under `triage`; the
  MCP endpoint and headers move under `investigation` and take three strings
  rather than the `DatadogConnection` type. `app/composition.py` resolves the
  connection once and hands those strings across, preserving the guarantee
  that a deployment able to fetch alerts is able to investigate them.
- **`ports/config.py` splits.** The nine settings value objects and the
  `Config` protocol become the `configuration` context; only the protocol was
  ever a port.
- **`fan_out/resolution.py` moves to the composition root**, which its own
  docstring has been waiting for. It is the only adapter that names sibling
  adapters.
- **Tests mirror the context tree.** `tests/unit/` and `tests/integration/`
  gain per-context packages, with files still named for behaviour rather than
  for modules. Scope markers keep coming from the top-level directory.
- **The architecture contracts grow** from three to per-context hexagons plus
  cross-context isolation.
- No production behaviour changes. The suite stays green at every step.

## Capabilities

### New Capabilities

None. This is a structural change; every behaviour it touches is already
specified.

### Modified Capabilities

- `project-conventions`: the machine-enforced import boundary is currently
  stated as one global domain/ports/adapters layering. It becomes one hexagon
  per bounded context plus rules that contexts may not reach into each other's
  internals and that the shared kernel depends on nothing. Adds a convention
  for locating a module's tests.

## Impact

- Every module under `src/alert_triage/` moves; `src/alert_triage/adapters/`
  and `src/alert_triage/ports/` are removed as packages.
- Every test file moves. `tests/conftest.py`'s directory-based scope marking
  is unaffected.
- `pyproject.toml`: the import-linter contract set is rewritten; the
  `forbidden_modules` vendor list is re-pointed at the new module paths.
- `README.md`'s architecture diagram and its guide for adding an adapter both
  describe a layout that no longer exists.
- No dependency, no CLI, no configuration key, and no external interface
  changes.

## Out of Scope

- Slice 8's evaluation harness. This change makes a home for it; it does not
  build it.
- Splitting the domain by entity/value-object/service stereotype. Concepts,
  not stereotypes, are what the contexts are organised by.
- Centralising the per-adapter environment settings modules. A deployment fact
  needed by exactly one adapter stays with that adapter.
