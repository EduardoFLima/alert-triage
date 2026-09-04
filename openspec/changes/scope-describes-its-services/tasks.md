## 1. Configuration describes a service

- [x] 1.1 Red: in `tests/unit/configuration/test_settings.py`, assert
  `ScopedService("checkout")` carries no acceptable latency and is not
  critical, and that `Scope("sre")` watches no named services. Watch it fail
  for want of the type.
- [x] 1.2 Green: add `ScopedService` to `configuration/settings.py` with
  `name`, `acceptable_latency_ms: int | None = None`, `critical: bool = False`,
  and give `Scope` a `services: tuple[ScopedService, ...] = ()`.
- [x] 1.3 Red: in the loader tests, read a `scope.services` list of two entries
  — one bare name, one with both keys — and assert what resolves. Add a test
  that an entry naming no service raises `ConfigError` identifying that entry.
- [x] 1.4 Green: read the list in `_scope`, refusing a nameless entry, and
  resolve each entry through the existing `_supplied` path so unknown keys stay
  refused by name.
- [x] 1.5 Red: set `SCOPE_SERVICES_CHECKOUT_CRITICAL=false` for a service the
  file declares critical and assert it resolves as not critical. Watch it fail
  — `bool("false")` is `True`. Add a second test that a value that is neither
  true nor false raises `ConfigError` naming the variable.
- [x] 1.6 Green: teach `_coerce` a `bool` case accepting `true/false/yes/no/1/0`
  case-insensitively and refusing the rest by name, and unwrap `X | None` to
  `X` so `acceptable_latency_ms` coerces as an int.
- [x] 1.7 Red: set `SCOPE_SERVICES=checkout,payments` against a file naming a
  different set, and assert the environment's set wins while each named
  service's settings still come from its file entry where one exists.
- [x] 1.8 Green: read `SCOPE_SERVICES` as a comma-separated list of names that
  replaces the file's set, per design.md.

## 2. An alert carries what it fired at

- [x] 2.1 Red: in the `Alert` tests, assert an alert built with an observed
  latency exposes it, and one built without exposes `None` — distinguishable
  from `0`. Watch it fail for want of the field.
- [x] 2.2 Green: add the optional observed latency in milliseconds to
  `triage/domain/alert.py`, defaulting to `None`.
- [x] 2.3 Add a grouping test that two alerts differing only in observed
  latency still group together, and extend the existing "grouping ignores the
  added fields" test to name it. This one guards rather than drives — say so
  in the commit rather than pretending it was red.

## 3. Ingestion narrows what it fetches and reads what triggered it

- [x] 3.1 Red: drive `DatadogAlertSource` with a scope naming two services and
  canned events covering three, and assert only the two are returned.
- [x] 3.2 Green: filter retrieved alerts against the scope's service names in
  the adapter, unconditionally — the port's guarantee does not rest on query
  syntax (design.md).
- [x] 3.3 Red: assert the request body's query narrows to the named services,
  and that a scope naming none leaves today's owner-only query untouched.
- [x] 3.4 Green: compose the service terms into the query as the optimisation
  it is, leaving 3.2's filter in place.
- [x] 3.5 Red: feed canned events whose account states a triggering latency in
  milliseconds and in seconds, and assert both translate to the same
  millisecond figure.
- [x] 3.6 Green: add the reader — a number with a time unit, identified as a
  latency by its surrounding text, normalised to milliseconds.
- [x] 3.7 Red: feed an event stating no measurement, one stating an error count
  or a percentage, one stating two candidate figures, and one whose account is
  unparseable alongside a readable sibling. Assert every alert is still
  returned and each of the four carries no latency.
- [x] 3.8 Green: make the reader yield nothing on all four, per design.md's
  "deliberately timid".

## 4. An incident within its acceptable latency is left alone

- [x] 4.1 Red: in the policy tests, decide against an incident whose every
  alert is at or under its service's acceptable latency and assert
  `should_report` and `should_investigate` are both false.
- [x] 4.2 Green: take the `ScopedService` in `policy.triage` and let the
  acceptable-latency check join the cooldown as a second reason a report is not
  due — not a third flag on `TriageDecision` (design.md).
- [x] 4.3 Red: cover the four cases that must not silence — one alert above the
  figure, one alert reporting no latency, a service declaring no acceptable
  latency, and an incident that absorbs a quiet alert after being investigated
  for a loud one.
- [x] 4.4 Green: make them pass, and confirm 4.1 still does.
- [x] 4.5 Red: in the pipeline tests, run a silenced incident end to end and
  assert nothing is investigated, nothing is delivered, the incident is
  recorded with its alerts absorbed and its report stamp and attempts
  untouched, and the run finishes successfully.
- [x] 4.6 Green: have `_handle` resolve the group's service from
  `config.scope` once — a bare `ScopedService(name=...)` when the scope names
  none — and pass that value to the decision, the target, and the report
  builder.
- [x] 4.7 Red: assert the run's account names the silenced incident and gives
  the acceptable latency as the reason.
- [x] 4.8 Green: add the journal line beside the existing "nothing is
  delivered" reasons.

## 5. Closing follows the same question

- [x] 5.1 Red: assert an incident left alone as within its acceptable latency,
  never reported, closes once its latest alert is older than the grouping
  window.
- [x] 5.2 Red: assert an incident that has never been reported because its
  investigations failed while attempts remain still does **not** close on age.
  This must pass before and after 5.3 — it is the behaviour the current
  `last_reported_at is None` guard exists for.
- [x] 5.3 Green: replace that guard in `is_closed` with the same "is a report
  due" question the run asks, so both cases fall out of one rule.

## 6. Criticality reaches the investigation and the report

- [x] 6.1 Red: assert `Incident.investigation_target` states criticality for a
  critical service and states it false otherwise.
- [x] 6.2 Green: add the field to `InvestigationTarget` in
  `investigation/contract.py` and take the `ScopedService` where the target is
  built.
- [x] 6.3 Red: assert a report for a critical service marks it in the subject,
  that an ordinary service's subject is byte-for-byte what it is today, and
  that the marking never lands in the body's place.
- [x] 6.4 Green: mark the subject in `triage/domain/report.py` beside
  `SUBJECT_PREFIX`, for both the investigated and the pass-through report.
- [x] 6.5 Extend the Diagnostician's instruction to say the target may be
  critical and what that licenses — look harder, never be surer — in the terms
  the `investigation` delta uses.
- [x] 6.6 Red: assert criticality changes no cadence — a critical service
  inside its cooldown is still not reported, and one within its acceptable
  latency is still left alone.

## 7. Remove what a service used to be described by

- [x] 7.1 Delete `CriticalService` from `configuration/settings.py`, the
  `critical_services` property from `configuration/port.py`, and
  `_critical_services` from the loader.
- [x] 7.2 Red: assert a `config.yaml` carrying a `critical_services` section is
  refused at startup naming the key, rather than starting with it dropped.
  Confirm this falls out of the existing unknown-key refusal rather than
  needing a case of its own.
- [x] 7.3 Update every test fake `Config` that declares `critical_services`
  (`tests/unit/app/*`, `tests/unit/configuration/*`,
  `tests/integration/configuration/*`) and delete the assertions that only
  existed for the removed section.

## 8. Say so everywhere a service is described

- [x] 8.1 `config.example.yaml`: replace the commented `critical_services`
  block with `scope.services`, showing a bare entry and one with both keys, and
  noting that a non-empty list narrows what is watched.
- [x] 8.2 `docs/configuration.md`: add `scope.services` to the behavior block
  and the `SCOPE_SERVICES` variable to the override section.
- [x] 8.3 `README.md`: reword where it describes what a run watches.
- [x] 8.4 `docs/vision.md`: replace the *Escalation* section with one on scoped
  services; rewrite slice 11; reword slice 12's "trip → partial report +
  auto-escalate" and the acknowledgement entry's "not the escalation path
  (slice 11)"; add the escalation path to *Explicitly deferred*; update the
  `critical-services registry` mention under Ports and the `critical_services`
  bullet under Config file.
- [x] 8.5 Confirm no new file is read at runtime, so the `Dockerfile`'s
  copy-by-name list is unchanged — and say so rather than assuming it.

## 9. Prove it

- [x] 9.1 Add a credential-gated live test per `docs/live-testing.md` asserting
  the latency reader against real monitor events on a real account, covering a
  latency monitor and a non-latency one. The change is not done until it has
  run; if it cannot be run, say so plainly.
- [x] 9.2 Add a credential-gated live test that a scope naming services fetches
  only those services, so the narrowed query is established against the real
  query grammar rather than against a canned body.
- [x] 9.3 Run the four gate commands — `uv run ruff check src tests`,
  `uv run ruff format --check src tests`, `uv run mypy`, `uv run pytest` — and
  confirm all four pass.
- [ ] 9.4 Confirm the container tests still pass, since the config schema they
  exercise has changed.
