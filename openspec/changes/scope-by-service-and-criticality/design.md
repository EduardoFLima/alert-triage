## Context

See `proposal.md` — Why. Three constraints shape the approach:

- `critical_services` has no consumer, so removing it costs nothing but text.
- `scope.owner` has exactly one consumer: the composed Datadog event query.
- The loader derives every environment variable mechanically from a setting's
  path, and coerces only scalars. `scope.services` is the first mapping-valued
  setting that must be reachable from the environment.

## Goals / Non-Goals

**Goals:** one rule for what a run watches; criticality reaching the crew's
reasoning and the report's wording through a single field; a file-less
deployment able to scope by service.

**Non-Goals:** merging environment and file service sets; a general mechanism
for structured environment values beyond the one shape this needs; wrapping
the loader's existing unwrapped `ValueError`s.

## Decisions

**Scope is a conjunction of optional filters.** Both keys narrow; naming
services within an owner watches those services *of* that owner. The
alternative was a union — owner's alerts *plus* the named services whoever
owns them — which reads more naturally from the word "complement" but leaves
`scope` unable to express "only these two services of my team", the thing
actually wanted. The cost is stated under Risks.

**A mapping keyed by service name, not a list of objects.** The key *is* the
name, so "an entry must name a service" needs no validation and no test. It
also matches the two sections that already have this shape
(`investigation.specialists`, and `critical_services` before it), and the
loader's path-to-variable derivation falls out of it unchanged — a list would
need index-addressed variables (`SCOPE_SERVICES_0_CRITICAL`), which name
nothing an operator can reason about.

**`SCOPE_SERVICES` replaces the file's section rather than merging.** One
sentence to document and no ordering to reason about. Merging is more useful
in the narrow case and much more surprising in general: an operator who sets
`SCOPE_SERVICES` would get services they did not name. The variable holds
comma-separated names; per-entry variables
(`SCOPE_SERVICES_<NAME>_CRITICAL`) then adjust whichever set resulted.
Rejected alternatives: encoding criticality into the one variable
(`checkout!,cart`), which invents an undiscoverable grammar; and JSON or YAML
in the value, which is complete but forks the documented promise that a
variable holds a scalar.

**Criticality rides `InvestigationTarget`.** `_brief`, which the report writer
receives, is built on `target.describe()` — so one field plus one line in
`describe()` reaches both the diagnostician driving the specialists and the
agent wording the report. The alternative, a report-only badge, is cheaper but
never reaches the reasoning, which is the part asked for. It defaults to false,
so the three-field callers that exist keep working.

**"At least one" is enforced in the loader, not in `Scope.__post_init__`.**
The mandatory-scope failure has the best error message in the project and must
keep it: the loader raises `ConfigError`, which `app/` already refuses to start
on. A dataclass `ValueError` would escape unwrapped, the way
`Investigation.max_attempts` already does. Fixing that inconsistency is a
separate change; this one does not depend on it.

**A removed section is discoverable because every unknown section now is.**
The loader validated keys *within* a section and ignored unknown sections
outright, so `critical_services` would have gone quiet rather than refused. A
shim knowing that one name would age into a list of names nobody deletes; the
general rule costs one check and answers the same question for the next
removal. The cost is that a connection setting written into `config.yaml` —
until now documented as inert — is refused, which the two tests asserting that
inertness are rewritten to say. That reads as the stronger promise: a
credential in the behavior file stops the run rather than leaving it to fail
on the first fetch.

**Escalation is removed, not deferred.** Slice 12's tripped breaker produces a
partial report marked incomplete and stops there — the "auto-escalate" half
had nowhere left to go. `docs/vision.md` references it from six places, and
leaving any of them would leave the vision describing a path no slice builds.

## Risks / Trade-offs

**Listing one service to mark it critical silently narrows the run to that
service.** → Intersection makes this structural, so it is a documentation
problem rather than a code one: `config.example.yaml` and
`docs/configuration.md` state, at the `services` key itself, that naming any
service narrows triage to the named services. The alternative — a separate
list for criticality — is the section being deleted.

**An empty `scope.services` could reduce a run to watching nothing while still
exiting `0`.** → Specified as unset rather than as a filter matching nothing,
with a scenario for the mapping-empty-and-no-owner case, which is the one a
naive check gets wrong.

**`SCOPE_SERVICES` discards criticality the file recorded for services it does
not name.** → Accepted, and the direct consequence of replace-not-merge. The
per-entry variable restores it in one line.

**The composed query changes shape**, gaining a service term alongside `team:`.
→ Per `AGENTS.md` this class of change is established only against a real
account; unit tests pass against the fake either way. A live test is a task,
and its result is reported plainly whether or not it was run.

## Open Questions

- Which form the platform's service term takes when several services are named
  — one grouped term or several OR'd terms. Both express the same filter and
  the choice is settled at the adapter against a real account, changing no
  requirement, no setting, and no other task.
