## Why

Investigation has one specialist. A triage report drawn from logs alone can say
what a service complained about, never whether it was slow, what a slow request
spent its time on, or whether the host underneath it ran out of memory — which
is most of what the first-pass legwork in `docs/vision.md` is supposed to cover.

Slice 8 in `docs/vision.md`. It comes first of the three investigation slices
because the Diagnostician that follows chooses between specialists, and a
manager with one specialist to choose from has nothing to decide.

## What Changes

- **Three specialist declarations**, one file each beside `logs.py`, following
  the pattern it established — instruction, output schema, toolsets, no model
  of its own:
  - **APM** — golden signals over the incident's window, single-hop upstream
    and downstream dependency evidence, and whether a change landed just before
    the alerts. Reaches `get_datadog_metric` and
    `search_datadog_service_dependencies` on `core`, plus
    `apm_latency_bottleneck_summary` and `get_change_stories` on `apm`.
  - **Trace** — finds the slow or failed requests and describes what one spent
    its time on. Reaches `search_datadog_spans` and `get_datadog_trace` on
    `core`.
  - **Infrastructure** — CPU, memory, disk and network around the window, and
    the workload underneath the service where there is one. Reaches
    `get_datadog_metric` and `search_datadog_hosts` on `core`, plus
    `search_datadog_k8s_resources` and `describe_datadog_k8s_resource` on
    `kubernetes`.
- **`Signal` gains `APM`, `TRACE` and `INFRASTRUCTURE`.** Additive; nothing
  reads the enum exhaustively.
- **Two specialists reach more than one toolset**, which no specialist has done
  before. The declaration already models it; the agent builder already opens one
  connection per toolset. What is new is that the path now runs.
- **A specialist may legitimately find its signal absent.** A service not on
  Kubernetes is not a failed retrieval, and the run must not mark every
  investigation on such a deployment incomplete. This is the failed-search gate
  from slice 7 pointed the other way, and it is this change's gate.
- **The report stops claiming only logs were searched.** `NOTHING_NOTABLE` says
  "the logs around these alerts were searched", which becomes false the moment a
  second specialist runs.
- **The live check walks the crew** instead of naming the logs specialist, so a
  specialist added later cannot ship without its tool names being confirmed
  against the real server.
- **`config.example.yaml` gains the `investigation:` section** it never had.
  With four specialists, which names may be given a model of their own is an
  operator question, and the example is the only place it would be answered.
- **BREAKING for cost, not for interface**: every incident now runs four
  specialists rather than one, sequentially. Nothing calling the port changes.
  Slice 9 is what makes the crew selective; until then this is the price of
  covering four signals.

## Capabilities

### New Capabilities

None. Investigation already specifies what a specialist is and what one owes;
these are three more of them.

### Modified Capabilities

- `investigation`: adds a requirement per specialist, stating what each reports
  and the evidence it cites — the logs specialist has one and these are its
  peers. Adds a requirement that a signal genuinely absent from a deployment is
  an empty result rather than a failed retrieval, which nothing states today
  because nothing could produce it.
- `triage-run`: adds a requirement that a report names the signals its
  investigation examined. Nothing states this today because one specialist made
  the scope obvious; the code says "the logs were searched" and the spec never
  had to disagree with it.

## Impact

- New: three modules under `investigation/adapters/datadog/specialists/`, with
  unit tests beside them.
- Changed: `investigation/contract.py` (`Signal` members),
  `investigation/adapters/adk/crew.py` (`CREW`), `triage/domain/report.py`
  (wording), `config.example.yaml`, and the example-config test's `SECTIONS`.
- Changed: `investigation/adapters/adk/evidence.py`, where an empty result is
  currently indistinguishable from an unreadable one.
- The live, credential-gated test becomes crew-wide. It costs four platform
  calls and four model calls per run and is still skipped without credentials.
- No new dependency, no new configuration key, no CLI change, no ledger change,
  and no change to what the port takes or returns.

## Out of Scope

- **Choosing which specialists an incident needs.** Slice 9. All four run on
  every investigation here.
- **Per-specialist model defaults.** Every declaration takes the deployment's
  model. Whether trace waterfalls want a stronger one is a question slice 10's
  harness answers with evidence; guessing now is what that slice exists to
  prevent.
- **Grouping the report by signal, or any other formatting work.** Slice 9 moves
  report formatting into an agent. Only the sentence that has become untrue
  changes here.
- **Running the crew concurrently.** Four sequential specialists press on
  `max_investigation_duration_seconds`, and the evidence store is shared and not
  built for concurrent writers. Noted in design, fixed when it has to be.
- **Multi-hop dependency traversal, FinOps, and profiling.** Roadmap in
  `docs/vision.md`; the APM specialist stays at one hop.
