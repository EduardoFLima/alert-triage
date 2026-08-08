## Context

See proposal.md — Why. Slices 1 and 2 left a domain that groups alerts, a
`Config` port resolved from YAML and environment, and an `AlertSource` port
with a Datadog adapter. Grouping is stateless: `group_alerts` recomputes
`AlertGroup` values from whatever alerts the lookback window returned, so
nothing about a group survives the run that produced it.

That is the gap this slice fills, and it is also what shapes the design. An
`AlertGroup` has no identity — it is a service tag and a tuple of alerts,
recomputed from scratch each run. Slice 2 explicitly deferred a concern here:
the ingestion lookback is set deliberately wider than the run interval, so
consecutive runs *will* re-deliver the same alerts, and dedup is what makes
that safe rather than duplicative.

This slice is also the first to persist anything, so it sets a convention the
same way slice 2 set the boundary-translation one: where durable state lives,
and which side of the config/environment line its location falls on.

## Goals / Non-Goals

**Goals:**
- Give an incident an identity that is stable while it is alive, so that
  "already reported" is a statement about an incident rather than about a
  particular set of alert ids.
- Keep the decision — continuation, and report-versus-suppress — pure and in
  the domain, with the port responsible only for storage. A dedup rule that can
  only be exercised through a database is a rule nobody will confidently change
  later.
- Make the whole slice testable with a fake clock and no external service, as
  `docs/vision.md` asks of it.
- Leave the ledger usable by a future backend that is not SQLite, since the
  publicly-extensible goal applies to this port as much as to `AlertSource`.

**Non-Goals:**
- Wiring the ledger into a pipeline. There is still no composition root; slice
  5 builds it and is this port's first real consumer.
- Deciding what a report contains or how it is delivered — slice 4 and beyond.
- Concurrency. v1 runs one job at a time, manually; concurrent writers are a
  deployment-packaging concern (slice 12), noted under risks.
- Tracking a high-water mark of ingested time. Overlapping windows are made
  safe by dedup here, which is what slice 2 assumed; a real watermark is a
  separate optimisation and is not needed for correctness.

## Decisions

**Identity is generated, not derived from contents.** An incident gets an
opaque generated id when it opens, and keeps it as alerts are absorbed. The
alternative — keying on the service plus a fingerprint of the alert ids — was
considered and rejected: an incident that is still firing grows new alerts on
almost every run, so a content-derived key changes almost every run, which
means every run sees a "new" incident and the cooldown never suppresses
anything. The failure is silent and looks exactly like the bug this slice
exists to fix. Keying on the service alone was also considered; it dedups
correctly but collapses two genuinely different problems on one service into
one incident, and gives a report nothing stable to name. Generated identity
separates the two questions cleanly: *which incident is this* is answered by
the continuation rule, and *what is it called* is answered once, at birth.

**The continuation rule is the grouping rule, applied across runs.** A group
continues an incident when it shares the service and either shares an alert
`source_id` with it, or its earliest alert falls within the grouping window of
the incident's latest alert. The second clause is precisely the predicate
`_runs_within` applies inside a single run — which means a burst that straddles
a run boundary produces exactly the incident it would have produced had all its
alerts arrived together. Making cross-run continuation a *different* rule from
in-run grouping would mean the number of incidents depends on when the job
happened to run, which is not a property anyone can reason about. The
`source_id` clause is what makes overlapping lookback windows cheap: re-seen
alerts match by identity without depending on timing at all.

**The decision lives in the domain; the port only stores.** `domain/triage.py`
takes the freshly grouped `AlertGroup`, the incidents on record for its
service, the current instant, the grouping window, and the cooldown, and
returns the resulting incident plus whether it is due to be reported. The
`TriageLedger` port has two operations — retrieve the incidents on record for a
service, and record an incident — and no opinion about any of it. The
alternative, a port with a `should_report(group)` method, was rejected: it
pushes the cooldown arithmetic and the continuation rule into every adapter, so
a second backend has to reimplement the rule and can get it subtly wrong, and
the rule becomes untestable without a database.

**Generated ids and the current instant are injected, not taken from the
ambient world.** The decision function takes a `now` and an id factory. This is
what the spec's "decisions are made against a supplied instant" requirement
asks for, and it makes the cooldown testable at any point in time without
sleeping or patching. The composition root supplies `datetime.now(UTC)` and a
`uuid4`-based factory. Reading the clock inside the domain was rejected for the
usual reason — it makes every cooldown test either slow or a monkeypatch.

**SQLite, over `sqlite3` from the standard library.** It is durable across
processes, transactional, a single file to move or delete, and adds no
dependency — so the `forbidden_modules` contract stays untouched, and nothing
new comes within reach of the domain. A JSON file was considered and is
simpler, but read-modify-write of a whole document is exactly the shape that
corrupts under an interrupted run, and the atomic-write dance to avoid that is
more code than a `CREATE TABLE`. Two tables: incidents keyed by the generated
id, and their alerts keyed by incident id, so an incident's alerts come back
with the identity and provenance they were recorded with — the spec requires
that, and a report naming an incident without naming its alerts is not
actionable.

**The instant an incident closed is recorded, not recomputed.** Closure is
derivable from the incident's last alert, its last report, and the current
window and cooldown — but *deriving* it means the moment an incident closed
moves whenever an operator retunes those settings, so shortening the cooldown
would retroactively age records into deletion. Stamping `closed_at` the first
time an incident is observed closed makes retention measure a fixed elapsed
time from a fixed event, which is the only reading under which "kept for thirty
days" means anything to the person going back to look.

**Timestamps are stored as ISO-8601 UTC text.** SQLite has no datetime type.
Text is inspectable with any client, sorts correctly, and round-trips through
`datetime.fromisoformat` without a custom converter. Values are normalised to
UTC on write and returned timezone-aware on read, so a naive datetime never
escapes the adapter into cooldown arithmetic — which is where a naive/aware
mix would blow up at the worst moment.

**The connection is injected, the schema is created on demand.** The adapter
takes an already-open `sqlite3.Connection`, exactly as the Datadog adapter
takes an already-configured client, keeping the location resolution in the
composition root beside the `Config` port. It ensures its own schema with
`CREATE TABLE IF NOT EXISTS` on construction, so a first run against a fresh
deployment needs no migration step. Injection is also what puts the adapter's
tests in `tests/unit/`: a `:memory:` connection is in-process, stdlib, and
needs no filesystem, which is the line `AGENTS.md` draws. One integration test
covers what memory cannot — that a real file on disk is read back correctly by
a second connection.

**Closing and deleting are two separate events.** An incident *closes* when it
can neither be continued nor suppress a report — its latest alert is older than
the grouping window *and* its last report is older than the cooldown. Both
bounds already exist, so closing needs no configuration. It is *deleted* only
after a further retention period, defaulting to thirty days, because the
ledger is the only record of what was reported and when, and a human
investigating an incident days later has nowhere else to look. Deriving
deletion from the decision bounds instead would mean the record vanishes
roughly two days after an incident goes quiet, which is exactly the window in
which someone asks "did we get told about this?".

Splitting the two is what keeps the retention knob safe. The obvious failure of
a retention setting is an operator setting it shorter than the cooldown and
silently deleting incidents that are still suppressing reports, reintroducing
the duplicates this slice exists to prevent. That cannot happen here: retention
is measured from the moment an incident *closes*, and closing already requires
the cooldown to have elapsed. The two settings therefore compose rather than
compete no matter how they are set, which is why they are resolved
independently and the spec pins that independence with scenarios in both
directions.

**Closed incidents are filtered out at retrieval, not merely ignored.** The
ledger hands a decision only the open incidents for a service; retained
records are never offered to the continuation or cooldown logic at all. The
alternative — returning everything and having the domain skip the closed ones —
puts the retention concept into the decision rule, so every future consumer has
to remember to apply it and a missed check silently resurrects a months-old
incident. Making it unrepresentable is cheaper than making it checked.

**Deletion runs on write.** It is the only moment the ledger is already open
and holding a transaction, so it costs nothing extra, and it bounds growth
against the same event that causes growth.

**The storage location is environment-only, with a default.** It goes on the
deployment side of the line slice 2 drew: the same triage behavior runs from a
laptop, a container, and a scheduled job with the same `config.yaml` and three
different paths. Unlike credentials it gets a documented default, because a
manual v1 run should need no configuration beyond `scope`, and a filesystem
path is not a secret. Alternative considered: a YAML key with the usual
env-wins precedence — rejected on the same test that put `DD_SITE` in the
environment, and applying it consistently is the point of having drawn the line.

**A ledger failure is its own exception, defined beside the port.**
`TriageLedgerError` sits next to `TriageLedger` as `AlertSourceError` sits next
to `AlertSource`. This matters more here than for ingestion: a failed read that
returned an empty list instead of raising would look exactly like "nothing has
been reported yet", and would re-report every live incident. Making the empty
result mean only one thing is what the spec pins down.

## Risks / Trade-offs

- [Two runs overlapping in time could both open an incident for the same
  alerts, since the read-decide-write sequence is not atomic across the whole
  run] → Accepted for v1, which runs one job at a time from a developer's
  machine. SQLite's own locking keeps the file consistent; what is unprotected
  is the interleaving, not the data. Slice 12's packaging is where scheduled
  execution is defined, and the natural fix there is single-flight per
  deployment rather than a transaction spanning the pipeline.
- [The continuation rule reuses the grouping window, so widening the grouping
  window also widens what counts as the same incident across runs] → Intended,
  and stated as such: they are the same question asked at two moments. The risk
  is that it is not obvious from the config key's name, so the coupling is
  called out in the spec's continuation scenarios rather than left implicit in
  the code.
- [An incident that fires continuously for longer than the cooldown is reported
  repeatedly, once per cooldown period, which for a genuinely stuck service
  could feel like noise] → This is the specified behavior from
  `docs/vision.md`: a still-broken service is worth re-raising, and the
  operator's control is the cooldown itself. Escalation (slice 9) is the path
  for cases that need a different cadence.
- [Storing every alert absorbed into a long-lived incident means an incident
  that fires for days accumulates rows, and thirty days of retention now holds
  that history far longer than the incident itself lives] → Accepted. The
  ceiling is a month of one team's alerts in a SQLite file, which is small
  against any realistic alert volume, and the alerts are needed both for the
  report and for `source_id` matching. If it ever bites, capping the retained
  alerts per closed incident is an adapter-local change no other component
  sees.
- [Retained history is only reachable by opening the database file — there is
  no command that shows what was reported last week] → Accepted for this slice,
  which has no CLI to add one to. The retention decision is what makes such a
  command possible later; SQLite was chosen partly because any client can read
  the file in the meantime, and the schema is plain columns rather than an
  opaque blob for that reason.
- [The default storage path lands wherever the process happens to run from, so
  a run started in a different directory silently starts from an empty ledger
  and re-reports everything] → Real, and the reason the default is documented
  rather than incidental. Slice 5's runnable job is where the resolved location
  becomes visible at startup; a container fixes it to one path by construction.
