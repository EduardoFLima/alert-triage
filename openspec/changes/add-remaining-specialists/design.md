## Context

Slice 7 left the crew extensible on purpose: a specialist is a declaration,
`build_agent` reads it, and the coordinator learns no tool name. This change is
the first test of that claim — three declarations, no coordinator edit. See
proposal.md for motivation and `docs/vision.md` for the crew's shape.

Two things the logs specialist never exercised now run: a specialist reaching
more than one toolset, and a specialist whose signal may be absent from a
deployment entirely.

## Goals / Non-Goals

**Goals:**

- Three declarations that cost nothing but their own files and one line of
  `CREW`.
- An empty platform answer that stays distinguishable from a broken one.
- A live check that a fifth specialist inherits without anyone remembering to
  extend it.

**Non-Goals:**

- Any change to `AdkInvestigator`, `Retrieved`, the port, or the contract beyond
  three `Signal` members. If a declaration needs the coordinator edited, the
  claim slice 7 made was wrong and that is worth finding out here.
- Tuning instructions. They will be mediocre and unmeasurable until slice 10.

## Decisions

**Tool names come from the current server, not from recall.** The declarations
name `get_datadog_metric`, `search_datadog_service_dependencies`,
`search_datadog_spans`, `get_datadog_trace`, `search_datadog_hosts` on `core`;
`apm_latency_bottleneck_summary` and `get_change_stories` on `apm`; and
`search_datadog_k8s_resources` and `describe_datadog_k8s_resource` on
`kubernetes`. These were read from Datadog's published tool reference during
planning, but a document is not the server: the live test is what establishes
they exist and that the filter admits them, and it runs per specialist. The
`apm` toolset is marked Preview by Datadog, which is a live-test failure waiting
to happen rather than a reason to avoid it — the alternative is the APM
specialist losing bottleneck analysis and change correlation, which is most of
what makes it worth having.

**Each specialist keeps one toolset per group rather than one flattened list.**
`Toolset` is `(name, tools)` and `connection_for` opens a connection per
toolset, so APM and infrastructure open two each. Asking one connection for
`?toolsets=core,apm` would halve the connections and blur what a specialist
declared: the group is how the platform organises tools and the names are what
we filter on, and collapsing them loses the first. Two connections per
specialist is a cost worth measuring in slice 10, not a shape worth changing
blind.

**Every declaration takes the deployment's model.** The vision offers
per-specialist models and the trace specialist is the obvious candidate. Setting
one now would be a guess dressed as a decision, and slice 10 exists to replace
guesses like it with numbers. Operators can override any of the four by name
today; the declarations stay at `None`.

**An empty result stops counting as a failure.** `_failure_in` currently treats
`readable(result) is None` as a failed retrieval, which is right for a result
carrying nothing readable and wrong for a tool that answered "no resources
match". The two are distinguishable in the shapes that matter: a structured
answer of `[]` or `{"result": []}` is an answer, and only a result with no
readable content at all is a failure. `readable` already returns `[]` rather
than `None` for the first, so the fix is to stop conflating an empty collection
with `None` — and to add the test that says so, which is the gate on this
change. The alternative, letting the infrastructure specialist mark every
investigation on a VM-based deployment incomplete, would make the incompleteness
marker meaningless for exactly the deployments most likely to use this.

**The live test walks `CREW`.** Today it names `LOGS_SPECIALIST` twice.
Parameterising over the crew means a specialist added later cannot ship without
its tool names confirmed against the real server, which is the one thing no fake
establishes. It also costs four model calls per live run instead of one; that
run is credential-gated and manual, so the cost is a developer's, not CI's.

**The report names the signals it examined rather than counting specialists.**
`NOTHING_NOTABLE` becomes a sentence built from the signals present in the
crew's declarations, so it widens by itself. Deriving it from `Signal` members
instead would claim coverage of any signal declared but not yet crewed.

**The scope reaches the report through the composition root, not through an
import.** `triage.domain` may not import `investigation.adapters`, so the
report cannot read `CREW` itself and the sentence cannot be built where it is
worded. `build_report` therefore takes the signals examined as an argument, and
the composition root — the one place allowed to name an adapter — passes
`SIGNALS_EXAMINED`, derived from `CREW`. The alternative, carrying the signals
on `Findings`, is a contract change this slice ruled out and the slice that
makes the crew selective will want anyway: there what ran stops being what was
declared, and only the investigation can say which is which. Until then the two
are the same tuple, and the cheaper of them holds.

## Risks / Trade-offs

- **The `apm` toolset is Preview and may be renamed or withdrawn.** → The live
  test fails loudly with the toolset named. Falling back costs the APM
  specialist two tools and its declaration one edit; the golden signals come
  from `core` either way.
- **Four sequential specialists press on `max_investigation_duration_seconds`
  (300s).** → Nothing enforces that bound yet (slice 12), so the practical risk
  in this slice is a slow run rather than a tripped breaker. Concurrency is the
  obvious answer and is deliberately not taken: `Retrieved` numbers calls
  sequentially and is shared across the crew, so concurrent specialists would
  race on citation identifiers. Slice 9 reduces the pressure by not running
  every specialist, which is a better fix than making the evidence store
  thread-safe for a problem that may disappear.
- **Cost per incident quadruples.** → Stated in the proposal, unavoidable in
  this slice, and the reason slice 9 follows immediately.
- **Four specialists' findings arrive as one flat tuple.** → They are already
  grouped, because the crew is walked in order and each finding names its
  signal. This holds only while the crew is a fixed sequence; slice 9's router
  breaks it, and slice 9 is also where report formatting moves into an agent.
  Not worth defending here.
- **An instruction that names a tool the declaration omits, or vice versa.** →
  The logs specialist's unit tests already assert the two agree; each new
  specialist gets the same assertion, which is cheap and catches the most likely
  copy-paste error.

## Open Questions

- Whether `search_datadog_hosts` earns its place in the infrastructure
  declaration alongside `get_datadog_metric`, or whether metrics alone answer
  the resource question. Answerable from the live run's tool-call counts without
  changing anything else.
