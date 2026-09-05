Red / green / refactor, one cycle per behavior, per `AGENTS.md`. Each task
below that adds behavior starts with the failing test named in it.

## 1. Remove the escalation section

- [x] 1.1 Delete the `critical_services` tests first, so the suite stops
  asserting behavior that is going away:
  `tests/integration/configuration/test_yaml_config_loader.py`,
  `tests/unit/configuration/test_settings.py`, and
  `tests/integration/configuration/test_example_configuration.py`
- [x] 1.2 Delete `CriticalService` from `configuration/settings.py`,
  `Config.critical_services` from `configuration/port.py`, and
  `_critical_services` and its imports from the YAML loader
- [x] 1.3 Drop the `critical_services` config stubs from the four
  `tests/unit/app/` run tests
- [x] 1.4 Remove the `critical_services` block from `config.example.yaml` and
  from `config.yaml`
- [x] 1.5 Confirm `critical_services` is now an unknown key: a test showing
  the loader refuses a config that still sets it, naming the key

## 2. Scope grows a services mapping (file only)

- [x] 2.1 Failing test: a config naming services under `scope.services`
  resolves them, each with a name and a `critical` flag defaulting to false
- [x] 2.2 Add `ServiceScope` and `Scope.services` to
  `configuration/settings.py`; make `Scope.owner` optional
- [x] 2.3 Failing test: `critical: true` on an entry resolves as critical, and
  an entry written with no settings resolves as in-scope and not critical
- [x] 2.4 Read the mapping in the loader, refusing an entry that is not a
  mapping of setting keys, and refusing an unknown key within one
- [x] 2.5 Failing test: services alone satisfy scope — the run starts with no
  owner resolved from either source
- [x] 2.6 Failing test: neither key resolving refuses the run, with a message
  naming owner, services, or both
- [x] 2.7 Failing test: `scope.services: {}` with no owner refuses the run,
  as though the key were absent — the case a naive check gets wrong
- [x] 2.8 Enforce "at least one" in the loader's `_scope`, raising
  `ConfigError` (see design — deliberately not in `Scope.__post_init__`)
- [x] 2.9 Expose `Config.scope` unchanged in shape; confirm no consumer of
  `scope.owner` broke on it becoming optional

## 3. The environment declares the services

- [x] 3.1 Failing test: `SCOPE_SERVICES=a,b` with no config file resolves
  exactly those two services, neither critical
- [x] 3.2 Teach the loader to read a comma-separated set of names — its first
  mapping-valued environment override
- [x] 3.3 Failing test: `SCOPE_SERVICES` replaces the file's section entirely;
  a service the file declared critical is neither in scope nor critical when
  the variable does not name it
- [x] 3.4 Failing test: `SCOPE_SERVICES_<NAME>_CRITICAL` sets criticality on
  an entry, whether the set came from the file or from `SCOPE_SERVICES`
- [x] 3.5 Failing test: with `SCOPE_SERVICES` unset, the file's services and
  their settings stand

## 4. Ingestion filters on both

- [x] 4.1 Failing test: services alone bound the fetch — alerts for the named
  services are returned regardless of owner
- [x] 4.2 Failing test: both filters resolved means an alert must satisfy
  both; an alert for a named service owned by someone else is not returned
- [x] 4.3 Failing test: no alert satisfying both is an empty result, not a
  failure
- [x] 4.4 Compose the service term into the query in
  `triage/adapters/datadog/alert_source.py`, alongside `team:`; settle the
  grouped-vs-OR'd form (design — Open Questions)
- [x] 4.5 Pass the resolved services from `app/composition.py` into the
  adapter beside the owner
- [x] 4.6 Failing test: a critical service is fetched on the same terms as any
  other — criticality reaches nothing here

## 5. Criticality reaches the investigation

- [x] 5.1 Failing test: `InvestigationTarget` states criticality and defaults
  to not critical, so existing three-field callers keep working
- [x] 5.2 Add the field to `investigation/contract.py` and one line to
  `describe()` — which `_brief` is built on, so it reaches the diagnostician
  and the report writer from one place
- [x] 5.3 Failing test: `Incident.investigation_target()` carries criticality
  through from the resolved scope
- [x] 5.4 Thread the resolved services to wherever the incident builds its
  target, without the investigation context reading config of its own
- [x] 5.5 Failing test: an investigation reads criticality only from its
  target and consults no configuration
- [x] 5.6 Failing test: the written account identifies a critical service's
  incident as critical
- [x] 5.7 Failing test: two incidents differing only in criticality get the
  same specialists under the same bounds

## 6. Documentation

- [x] 6.1 Rewrite slice 11 in `docs/vision.md` — scoping by service and
  criticality, replacing the escalation path
- [x] 6.2 Remove escalation from the other five sites in `docs/vision.md`: the
  Config port description (~120), the `### Escalation` section (~370), the
  breaker trip's "routes through the escalation path" (~393), the
  `critical_services` config bullet (~449), the acknowledgement note (~667),
  and slice 15's diagram rationale (~889)
- [x] 6.3 Restate slice 12: a tripped breaker produces a partial report marked
  incomplete, and nothing escalates
- [x] 6.4 Document `scope.services` in `config.example.yaml` — stating at the
  key itself that naming any service narrows triage to the named services
- [x] 6.5 Update `docs/configuration.md` and `README.md` for the new scope rule
  and the `SCOPE_SERVICES` variables

## 7. Before calling it done

- [x] 7.1 `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy`, `uv run pytest` — all four green
- [ ] 7.2 Run the live tests against a real account per
  `docs/live-testing.md`, for the composed query the fake cannot establish —
  and say plainly in the report if they were not run
