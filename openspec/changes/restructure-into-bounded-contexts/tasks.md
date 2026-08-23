## 1. Semantic changes, in the current tree

Behaviour-affecting edits first, each its own red/green cycle, so they are
reviewable before any bulk move hides them.

- [x] 1.1 Red: assert `TriageReport` exposes `incident_id` and `service` as
      fields and no longer carries an `Incident`
- [x] 1.2 Green: replace `TriageReport.incident` with `incident_id: str` and
      `service: str`; drop the two derived properties; update `build_report`
      and its helpers to pass them through
- [x] 1.3 Update `tests/unit/test_report.py` and
      `tests/integration/test_end_to_end.py`, the only two places reading
      `report.incident`, to assert on `incident_id`
- [x] 1.4 Red: assert an investigation is requested with a target carrying
      service, window, and alert count, and that a failed investigation still
      names the service it concerned
- [x] 1.5 Green: add `InvestigationTarget`; retype `Investigator.investigate`
      to take it; add the `Incident` → target translation on the triage side
- [x] 1.6 Move `describe()` onto `InvestigationTarget` in the adk adapter and
      drop the adapter's remaining `Incident` imports from `specialists.py`
      and `investigator.py`
- [x] 1.7 Red: assert the MCP endpoint and headers are derived from site and
      key strings rather than from a `DatadogConnection`
- [x] 1.8 Green: retype `mcp_endpoint`/`mcp_headers` to take `site`,
      `api_key`, `app_key`; move the `DatadogConnection` → `Deployment`
      translation into `app/composition.py`
- [x] 1.9 Move `resolve_notifier` from `adapters/fan_out/resolution.py` into
      `app/composition.py`, deleting the module; `FanOutNotifier` stays
- [x] 1.10 Full gate green: `ruff check`, `ruff format --check`, `mypy`,
      `pytest`

## 2. Split the configuration model out of ports

- [x] 2.1 Create `configuration/` with `settings.py` holding the nine value
      objects from `ports/config.py`, `port.py` holding the `Config` protocol
      and `ConfigError`
- [x] 2.2 Move `adapters/yaml_config` and `adapters/env_file` to
      `configuration/adapters/{yaml,env_file}`
- [x] 2.3 Delete `ports/config.py`; update every importer
- [x] 2.4 Full gate green

## 3. Create the shared kernel and the context packages

- [x] 3.1 `git mv` `domain/window.py` to `shared/window.py`; update importers
- [x] 3.2 Create `triage/{domain,ports,adapters}` and move `incident`,
      `alert`, `grouping`, `report`, and `triage.py` (renamed `policy.py`)
      into `triage/domain`; `alert_source`, `triage_ledger` (renamed
      `ledger.py`), and `investigator` (renamed `investigation.py`) into
      `triage/ports`; `adapters/sqlite_ledger` into `triage/adapters/sqlite`
- [x] 3.3 Move `adapters/datadog/{connection,alert_source}.py` into
      `triage/adapters/datadog/`
- [x] 3.4 Full gate green
- [x] 3.5 Create `investigation/` with `contract.py` holding
      `InvestigationTarget` plus `Findings`, `Finding`, `EvidenceItem`, and
      `Signal` moved out of `domain/findings.py`
- [x] 3.6 Move `adapters/adk/{crew,model,credentials,investigator,evidence,
      normalisation}.py` into `investigation/adapters/adk/`; move the
      `Specialist` and `Toolset` declaration types into
      `investigation/domain/specialist.py` and the citation discipline into
      `investigation/domain/evidence.py`
- [x] 3.7 Move `adapters/datadog/datadog_mcp.py` to
      `investigation/adapters/datadog/mcp.py` and `adapters/adk/logs_agent.py`
      to `investigation/adapters/datadog/specialists/logs.py`
- [x] 3.8 Full gate green
- [x] 3.9 Create `notification/` with `contract.py` holding `TriageReport`;
      move `ports/notifier.py` to `notification/ports/`, and
      `adapters/{email,teams}` plus `fan_out/notifier.py` into
      `notification/adapters/`
- [x] 3.10 Rename `app/run.py` to `app/pipeline.py`; delete the now-empty
      `domain/`, `ports/`, and `adapters/` packages
- [x] 3.11 Full gate green

## 4. Rewrite the architecture contracts

Each contract is shown to fail before it is shown to pass — a contract that has
never failed has not been shown to enforce anything.

- [x] 4.1 Replace the single layers contract with one per context
      (`adapters` → `ports` → `domain`), demonstrating a red against a
      deliberate inward-pointing violation in each
- [x] 4.2 Add the forbidden contract stopping a context reaching past another's
      contract into its `domain` or `adapters`; demonstrate red
- [x] 4.3 Add the independence contract between `investigation` and
      `notification`; demonstrate red
- [x] 4.4 Add the forbidden contract stopping `shared` importing any context;
      demonstrate red
- [x] 4.5 Re-point `forbidden_modules` in the vendor-library contract and the
      `app.pipeline` contract at the new module paths; confirm both still go
      red on a deliberate violation
- [x] 4.6 Full gate green with every deliberate violation reverted

## 5. Mirror the test tree

- [x] 5.1 Create the per-context packages under `tests/unit/` and
      `tests/integration/`; confirm `tests/conftest.py` still derives scope
      markers from the top-level directory
- [x] 5.2 Move the triage, configuration, and shared tests into their packages
- [x] 5.3 Move the investigation tests, resolving the three-way overlap between
      `test_adk_evidence.py`, `test_evidence_callback.py`, and
      `test_evidence_normalisation.py` into files named for the behaviour each
      establishes
- [x] 5.4 Move the notification tests; split `test_run.py` into
      `tests/unit/app/` files named for the arcs they cover
- [x] 5.5 Push shared fixtures down into the nearest `conftest.py` within each
      context's test package
- [x] 5.6 Full gate green, and confirm `pytest tests/unit/investigation` runs
      that context's tests alone

## 6. Documentation

- [ ] 6.1 Regenerate the `README.md` architecture diagram via the mermaid MCP
      tool to show the four contexts and their permitted edges
- [ ] 6.2 Update the README's adapter-extension guide: adding a platform is
      adding a directory under `investigation/adapters/`
- [ ] 6.3 Update `AGENTS.md`'s hexagonal-architecture section to describe
      per-context hexagons, the contract rule, and where a new runtime
      dependency is declared
- [ ] 6.4 Final full gate green
