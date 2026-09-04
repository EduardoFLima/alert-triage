## Context

See proposal.md — Why. Three constraints shape the approach:

- `Scope` today is one field, `owner`, and is the only mandatory setting. It
  is the only setting with no default and no fallback, because "watch
  everything" is not an answer a run may reach on its own.
  `critical_services` is a sibling `Mapping[str, CriticalService]` on the
  `Config` port that nothing outside configuration reads.
- The YAML loader derives every environment variable name mechanically from a
  key's path and coerces the string with `target(raw)`. It has never met a
  `bool` (`bool("false")` is `True`) nor an optional value, and it reads
  mappings keyed by name, never lists.
- A run already decides *is a report due* in one place, `triage.domain.policy`,
  and investigation, delivery, and closure are all expressed against that
  answer. Nothing else in the pipeline decides whether to act on an incident.

## Goals / Non-Goals

**Goals:**

- One place describes a service, and it is the same place that says which
  services are watched.
- The acceptable-latency decision reuses the run's existing notion of a report
  being due, rather than adding a parallel one.
- The scope filter is guaranteed by the port regardless of what any platform's
  query syntax supports.

**Non-Goals:**

- Any second delivery route, cadence, or urgency ranking. Criticality changes
  wording, never timing.
- Giving the investigation the acceptable latency as a baseline to reason
  against. It gates whether an investigation happens; it is not evidence.
- A general list-valued config schema. `scope.services` is the only list, and
  its handling stays local to reading it.

## Decisions

**`ScopedService` hangs off `Scope`; `critical_services` leaves the port.**
`Scope` becomes `owner` plus `services: tuple[ScopedService, ...]`, where
`ScopedService` is `name`, `acceptable_latency_ms: int | None = None`, and
`critical: bool = False`. The alternative — keeping `critical_services` and
adding `scope.services` beside it — was rejected in the proposal: two sections
describing one service is the duplication being removed, and the criticality
flag has no meaning apart from the service it is declared on.

**An owner and a list of services are two axes, and either alone is a scope.**
`scope.owner` stops being mandatory in its own right; what is mandatory is that
`scope` says *something* about what is watched. Owner alone watches everything
that owner owns, services alone watch those services whoever owns them, and
both together intersect. The alternative — keeping the owner mandatory and
making `services` a pure narrowing of it — forces a deployment that knows its
services to invent an owner it does not otherwise use, and an invented owner is
a query term that silently returns nothing. The rule lives on `Scope` itself as
well as in the loader: the loader's refusal is the one an operator reads,
because it can name the two settings and where each is read from, while the
value's own guard is what makes a scope that watches nothing unconstructible.

**The adapter filters locally and narrows the query as well.** Narrowing the
Datadog query with the service terms is what makes a scoped run cheap, but the
port's guarantee must not rest on a vendor's query syntax or on how long a
query may be. So the adapter drops any retrieved alert whose service is not in
scope, unconditionally, and treats the narrowed query as an optimisation over
that. The alternative, trusting the query alone, makes the requirement
unprovable without a live account and fails silently the day a service name
contains something the query grammar treats specially.

**Silence is expressed as "no report is due", not as a fourth flag.** The
acceptable-latency check joins the cooldown as a second reason `should_report`
is false, inside `policy.triage`. Investigation already follows from "due",
delivery already follows from "due", and `is_closed` already asks the same
question — so all three inherit the new behavior without an `if` of their own,
including the closure fix, where `last_reported_at is None` is replaced by the
due check it was always standing in for. The alternative, a separate
`should_silence` on `TriageDecision`, would have every consumer branch on two
answers that can never both be true.

**The pipeline resolves the service description once and passes the value.**
`_handle` looks the group's service up in `config.scope` once, defaulting to a
bare `ScopedService(name=...)` when the scope names no services, and hands that
value to `policy.triage`, to `Incident.investigation_target`, and to
`build_report`. Passing the value object rather than an
`acceptable_latency_ms`/`critical` pair keeps AGENTS.md's rule against boolean
parameters that select behavior, and means a third per-service setting later
changes no signature.

**Reading the latency is deliberately timid.** The Datadog adapter reads the
event's own account of what triggered it, matches a number with a time unit
where the surrounding text identifies it as a latency, normalises to
milliseconds, and yields nothing whenever more than one candidate is present or
the unit is absent. It never guesses, because the cost of a wrong reading is
one-directional: a missed latency costs an investigation nobody needed, while a
fabricated one silences an incident that mattered. This is exactly the kind of
change AGENTS.md says a green suite does not establish — it is pinned by a
credential-gated live test per `docs/live-testing.md`, and the change is not
done until that test has run against a real account.

**The environment learns two new tricks, both narrow.** `_coerce` gains a
`bool` case accepting `true/false/yes/no/1/0` and refusing anything else by
name — silently reading `SCOPE_SERVICES_CHECKOUT_CRITICAL=false` as critical is
the worst available outcome — and unwraps `X | None` to `X`. Separately,
`SCOPE_SERVICES` names the watched services as a comma-separated list,
replacing the file's set wholesale, with each named service's settings still
read from the file entry of that name and from per-key overrides. The
alternative, file-only declaration as `critical_services` had, leaves a
container unable to narrow its own scope — and slice 14 made containers a real
deployment target, where per-team values come from the environment.

**Criticality marks the subject from triage, not from the agent.** The Report
agent writes the headline; whether the service is critical is a configuration
fact about the service, not something an investigation found. So it joins
`SUBJECT_PREFIX` in `triage.domain.report` — the same reasoning that already
puts the sender's own marker there rather than in the agent's output.

**The vision is edited in this change, not before it.** `docs/vision.md` is the
source of truth for the slice order, so reformulating slice 11 is part of the
work rather than a precondition for it: the *Escalation* section becomes one
describing scoped services, the escalation path joins *Explicitly deferred*,
and the two entries that refer to it — slice 12's "trip → partial report +
auto-escalate" and the acknowledgement roadmap entry's "not the escalation path
(slice 11)" — are reworded to say what they mean without it.

## Risks / Trade-offs

**Reading a figure out of a vendor's prose is fragile, and Datadog may reword
it** → The reader yields nothing on anything it is not sure of, and nothing
means "investigate as usual". A regression therefore costs investigations that
were not needed, never silence that was not earned. The live test is what
notices.

**Scope filtering is a breaking change that can silence a whole deployment** →
An operator who moves their `critical_services` entries into `scope.services`
verbatim would narrow their scope to the services they had called critical,
which is not what they meant. The removed requirement's Migration says so
explicitly, and the run's own account names the services it is watching, so a
run that suddenly fetches nothing says why on its first line.

**Criticality reaching the Diagnostician invites anchoring** → The investigation
delta forbids the two forms that would matter — a higher confidence for the same
evidence, and a hypothesis offered because the service is important — and the
instruction states the bound in those terms. Whether it holds is a question for
the evaluation harness, which is the roadmap item that exists to answer exactly
this kind of question.

**An incident silenced today can be un-silenced by an operator lowering the
threshold tomorrow** → Accepted, and correct: the incident stays open and keeps
absorbing alerts while it is inside the grouping window, so lowering the
threshold makes the next run investigate the incident already on record rather
than a fresh one. Raising the threshold cannot retroactively silence an
incident already reported, because a delivered report is stamped.

## Migration Plan

Configuration only; there is no stored state to migrate. `critical_services`
becomes an unknown key, which the loader already refuses by name, so a
deployment carrying one fails at startup with the key named rather than
starting with a setting silently dropped. `config.example.yaml` and
`docs/configuration.md` carry the replacement, and the removed requirement in
the `config` delta carries the mapping. Rollback is reverting the commit: no
schema, ledger, or report format changes shape.

## Open Questions

- Should `acceptable_latency_ms` also reach the investigation as the baseline a
  specialist judges what it measures against? It is a plausible second use of
  the same number, but it is a different feature — evidence rather than a gate —
  and the evaluation harness is what should say whether it improves anything.
  Deferring it changes nothing here.
- Should criticality raise the consultation budget for an incident? That budget
  is slice 12's to make configurable, and deciding it now would place a setting
  in a section slice 12 is about to move.
