## 1. Alert entity

- [x] 1.1 Write failing tests for an `Alert` entity constructed from a
      service tag and a timestamp (specs/alert-grouping - Alert entity)
- [x] 1.2 Implement `Alert` in the domain layer to pass those tests

## 2. Grouping logic

- [x] 2.1 Write failing tests for same-service/same-window grouping
      (specs/alert-grouping - Same-incident grouping): same service + within
      window groups together; different service does not; same service but
      outside window does not
- [x] 2.2 Write failing tests asserting a group of N alerts is exposed as one
      group, not N (specs/alert-grouping - One group, one investigation)
- [x] 2.3 Implement the grouping function/module to pass those tests, taking
      the grouping time window as a parameter rather than a hardcoded value

## 3. Config port

- [x] 3.1 Write failing tests for the `Config` port's shape (interface/
      protocol) that later adapters and consumers depend on
- [x] 3.2 Define the `Config` port in the domain layer

## 4. YAML + env loader adapter

- [x] 4.1 Write failing tests: no `config.yaml` present resolves without a
      missing-file error (specs/config - Optional config file)
- [x] 4.2 Write failing tests: `circuit_breakers` resolves to documented
      defaults when omitted (specs/config - Defaults for optional sections)
- [x] 4.2a Write failing tests: omitting `critical_services` entirely means
      no service is treated as critical (specs/config - Optional
      critical_services section)
- [x] 4.2b Write failing tests: a service listed under `critical_services`
      with only some threshold keys set is still treated as critical, keeps
      its explicit values, and gets documented defaults for the keys it
      omitted (specs/config - Threshold defaults within a declared critical
      service)
- [x] 4.3 Write failing tests: `scope` resolves from config-file-only,
      env-var-only, and fails to start when absent from both (specs/config -
      Mandatory scope with no fallback)
- [x] 4.4 Write failing tests: env var overrides a YAML value for `scope` and
      for a non-scope value, following the `section.key` → `SECTION_KEY`
      mapping (specs/config - Environment variable overrides for any config
      value)
- [x] 4.5 Implement the YAML/env adapter satisfying the `Config` port: parse
      optional `config.yaml`, apply section defaults, resolve the mechanical
      env-var-name mapping, merge with env-first precedence, raise at
      startup if `scope` is unresolved
- [x] 4.6 Add the grouping time window as an optional config key with a
      documented default, resolved through the same loader

## 5. Verification

- [x] 5.1 Run the full test suite and confirm all new tests pass with no
      regressions
- [x] 5.2 Confirm domain code (Alert, grouping, Config port) has no import
      of the YAML/env adapter or any other outward-facing dependency,
      consistent with the hexagonal layout
