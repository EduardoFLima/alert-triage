## Why

Slices 1–4 built four working pieces that have never met: alerts can be
fetched, grouped, decided upon, and delivered, but nothing calls them in
order. There is no composition root, no entrypoint, and no way for a human to
run this project at all — every capability so far is exercised only by its own
tests.

This is slice 5 of the capability breakdown in `docs/vision.md`: wire
ingestion → grouping → ledger → notifier with a trivial pass-through report,
and make the result the first runnable manual job. It is deliberately built
before investigation (slice 6+), so that the pipeline's shape, its ordering
guarantees, and its failure behavior are settled and tested while the thing
flowing through it is still trivial.

## What Changes

- Add a **composition root** in `app/`: the one place where `load_config`,
  `resolve_connection`, `build_alert_source`, `resolve_ledger_path`,
  `SqliteTriageLedger`, and `resolve_notifier` are named and assembled. Every
  existing adapter already exposes exactly the factory this needs; none of
  them changes.
- Add a **triage run**: fetch alerts over the configured lookback, group them,
  and for each group consult the ledger, reach a triage decision, deliver a
  report when one is due, and record the incident. The run is a single pass
  that starts, does its work, and exits — the job shape v1 deploys as.
- Add a **console entrypoint** (`alert-triage`) so the job runs with one
  command, plus `python -m alert_triage`, and document it in the README.
- Add a **pass-through report**: a `TriageReport` built from the incident
  alone — its service, how many alerts it absorbed, when they fired, and links
  back to them. It is honest about being untriaged. Slice 8's Report agent
  replaces the body and nothing else in this slice changes when it does.
- **Move the "reported" stamp to after delivery.** Today `triage()` returns an
  incident already stamped as reported, which was correct when nothing could
  deliver anything. Now that a delivery can fail, stamping before it happens
  would start a cooldown on a report nobody received and suppress the retry
  the next run owes the team. The decision keeps saying *whether* to report;
  the caller stamps the incident once a channel has accepted it.
- **Isolate failures per group.** One service's ledger error or failed
  delivery must not cost the other services in the same run their reports; the
  run continues and reports what it could not do at the end, through its exit
  status. A failed *fetch*, by contrast, ends the run — there is nothing to
  work on.
- Make the run's instant a single value, taken once at the start and passed
  down, so the lookback bound, every cooldown decision, and every recorded
  timestamp agree with each other.

## Capabilities

### New Capabilities
- `triage-run`: the end-to-end run — the order the stages execute in, what a
  run does when a stage fails, that a report is delivered before its incident
  is recorded as reported, the single instant a run decides against, the
  pass-through report's content, the composition root as the only place
  adapters are named, and how a human invokes the job and reads its outcome.

### Modified Capabilities
- `triage-ledger`: an incident is recorded as reported only once a channel has
  accepted the report. The cooldown rule itself is unchanged; what changes is
  the moment the stamp is applied, and therefore that a run which could not
  deliver leaves the incident due for report in the next run.

## Impact

- New `app/` modules: a composition root that builds the dependencies, and a
  run that takes them as arguments and knows no adapter. Import-linter already
  allows `app` to reach every layer, so no contract changes.
- New pass-through report builder in `domain/` — stdlib-only, replaceable by
  slice 8 without touching the pipeline.
- `domain/triage.py`: `triage()` no longer stamps the incident it returns.
  This is the only behavioral change to existing code, and its unit tests move
  with it.
- `pyproject.toml` gains a `[project.scripts]` entry. No new runtime
  dependency: every adapter this wires together already exists.
- New end-to-end tests in `tests/integration/` driving the run through fakes
  for all three ports, plus unit tests for the pass-through report and the
  run's ordering and failure rules.
- README gains a "Running it" section naming the command and what a run
  needs in its environment. `docs/vision.md` is unchanged: this slice
  implements what it already describes.
