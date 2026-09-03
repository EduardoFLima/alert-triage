## Why

Slice 11 as `docs/vision.md` states it — an escalation path with a
severity/threshold rule that bypasses batching and notifies immediately — buys a
second delivery route, a second cadence to tune, and an urgency ranking, none of
which a PoC has evidence for. Its config half has been in the schema since slice
1 with nothing reading it, and the one threshold it declares,
`critical_services.<service>.latency_threshold_ms`, names a number no `Alert`
carries: a rule meant to fire *before* an investigation has no value to evaluate
until one has run.

What the running system actually lacks is smaller. A run watches everything one
owner owns and knows nothing about the services it watches — not which of them
are worth watching, not what "slow" means for any of them, and not which of them
a human should look at first. So slice 11 becomes: **scope describes the
services it watches**, and the escalation path moves to the roadmap.

## What Changes

- `scope` gains an optional `services` list. Each entry MUST name a service and
  MAY carry `acceptable_latency_ms` and `critical`.
- **BREAKING** A non-empty `services` list narrows what a run watches: only the
  listed services are fetched and triaged. Absent or empty means every service
  the owner owns, which is today's behavior and stays the default.
- `Alert` gains an observed latency, read by the Datadog adapter from the
  monitor event's own account of what triggered it, and absent where none can be
  read.
- An incident is left alone when every alert in it reports a latency at or under
  its service's `acceptable_latency_ms`: no investigation, no report. It is
  still recorded, so an overlapping run recognises it rather than opening a
  second incident. An alert with no readable latency is never "under" anything,
  so an incident holding one is investigated as usual — silence is only ever
  chosen against a number that was actually read.
- Closing follows. Today an incident that was never reported never closes,
  because being unreported means owing a report — which stops being true for one
  the system deliberately left alone. Closure asks whether a report is *due*
  rather than whether one has *happened*, which is the same question the run
  already asks, so a silenced incident closes on age like any other and the
  ledger stays bounded.
- `critical` travels to the investigation as a fact about its target, so the
  Diagnostician weighs the incident accordingly, and marks the delivered
  report's subject.
- **BREAKING** The `critical_services` section is removed, along with
  `CriticalService`, its `tier`, and its `latency_threshold_ms`. A service is
  described in one place.
- `docs/vision.md` is reformulated: the *Escalation* section is replaced by one
  describing scoped services, slice 11 is rewritten, slice 12's "auto-escalate"
  and the acknowledgement roadmap entry's reference to "the escalation path
  (slice 11)" are reworded, and the escalation path itself joins *Explicitly
  deferred*.

Out of scope, and deliberately: alert severity as a field, an immediate
"needs a human now" delivery route, urgency tiers, any second cadence, and
anything that would let `critical` change *when* a report is delivered rather
than how it reads.

## Capabilities

### New Capabilities

None. Every requirement lands in a capability that already exists — which is
itself evidence the reformulation is the smaller change.

### Modified Capabilities

- `config`: `scope` gains the optional `services` list, its per-entry keys, and
  the rule that a named entry is mandatory-`name`; the `critical_services`
  requirements are removed.
- `alert-ingestion`: "Only alerts within the configured scope" narrows from the
  owner alone to the owner and, when declared, the listed services; translation
  populates the observed latency where the platform's account of the alert
  carries one.
- `alert-grouping`: the `Alert` entity carries an observed latency, which
  grouping ignores as it ignores the other reporting fields.
- `triage-run`: an incident whose alerts are all within the acceptable latency
  is neither investigated nor reported, and is still recorded; a critical
  service's report says so.
- `triage-ledger`: an incident closes once no report is due for it and its
  alerts have aged past the grouping window — which reaches the incident nobody
  was ever owed a report about, where "never reported" alone did not.
- `investigation`: an investigation is told whether its target is a critical
  service, and the Diagnostician is entitled to weigh that.

## Impact

- `configuration/settings.py` — `ScopedService` added to `Scope`;
  `CriticalService` deleted. `configuration/port.py` — `critical_services`
  removed. `configuration/adapters/yaml/loader.py` — the list is read, entries
  are keyed by name for environment overrides, and a missing `name` is refused.
- `triage/domain/alert.py` — the observed-latency field.
  `triage/domain/policy.py` — the acceptable-latency decision, and `is_closed`
  asking it too.
  `triage/domain/incident.py` — criticality reaches the investigation target.
  `triage/domain/report.py` — the subject marks a critical service.
  `triage/adapters/datadog/alert_source.py` — the service filter in the query
  and the latency reading.
- `investigation/contract.py` — `InvestigationTarget` gains criticality;
  `adapters/crew/reasoners/diagnostician.py` — its instruction weighs it.
- `app/pipeline.py` — resolves the group's service entry once and hands it to
  the decision, the target, and the report builder.
- `config.example.yaml`, `docs/configuration.md`, `docs/vision.md`, and
  `README.md` where it describes what a run watches.
- No new dependency, no new port, no change to `Notifier`, `AlertSource`, or
  `TriageLedger`, and no change to any exit code.
