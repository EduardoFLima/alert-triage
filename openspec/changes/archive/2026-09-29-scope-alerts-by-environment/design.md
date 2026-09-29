## Context

See proposal.md for why. The environment has to reach three places that
already receive the service: the alert query, the investigation target, and
every address built from either. Criticality took the same route from `scope`
to the target in an earlier change, and this follows it.

## Goals / Non-Goals

**Goals:**

- One place the environment is configured, and every downstream use reading
  it from what it was handed rather than from configuration.
- No composed link that silently widens to every environment of a service.

**Non-Goals:**

- Several environments per run, and a monitor link scoped by environment —
  both out of scope in the proposal.

## Decisions

**`env` is a plain string on `Scope`, defaulted to `"prod"` on the dataclass.**
The loader reads it through `_supplied` like any scalar, so `SCOPE_ENV` comes
for free from the path-derived naming. The at-least-one check in `_scope` is
untouched, which is what keeps env from satisfying scope. The alternative, a
mandatory env with no default, was rejected because the user asked for `prod`
as the default and most deployments watch production.

**The environment comes from `scope`, not from each alert.** Every alert the
source returns already carries the configured environment, because the query
asked for nothing else; reading `env:` off each alert's tags would add a field
to `Alert`, a column to the ledger and a mismatch case to handle, for a value
that is constant within a deployment. `Incident.investigation_target(scope)`
already takes `scope` for criticality and passes `scope.env` beside it. The
cost is the risk below.

**`InvestigationTarget.env` is `str | None = None`.** Defaulted so every
existing construction still compiles, the move `critical` made. `None` means
"no environment given", not "prod": the investigation context must not know
the configuration's default. `describe()` states the line either way, for the
reason criticality is always stated — silence is indistinguishable from
unclassified.

**Specialists are told once, in the shared dialect.** `dialect.py` already
says "always scope the query to the service you were told about" and already
shows `{service:checkout,env:prod}` as an example. That sentence becomes
service *and* environment, and each specialist's own "scope to the service"
line follows. Enforcing env by rewriting tool arguments was considered and
rejected: it hides from the model what was actually asked, and a metric with no
`env` tag would then come back empty for a reason nobody can see.

**Retrieved addresses are not touched; composed ones are.** The Log Explorer
form copies the query that ran, so it carries env exactly when the specialist
used it — which is correct, since the address must open what was retrieved.
Forms composed from the target — the APM service page and trace explorer in
`address-evidence-where-it-came-from`, and the service-page link a finding's
section anchors — take `env` from the target: `?env=prod` on the service page,
`env:prod` in the trace explorer's query. Those forms do not exist yet; whichever
change lands second writes the env into them, and the task here is conditional
on that.

**The alert source spends env as one more conjunctive term**, `env:<name>`,
beside `team:` and `service:`, and adds it to the Event Explorer fallback
link's query. `build_alert_source` gains an `env` argument, passed from
`config.scope.env` at the composition root as owner and services already are.

**The report names env in a fragment the system writes.** An investigated
report's subject is the diagnosis headline, whose wording an agent owns, so
asking the headline to mention env would be a hope rather than a guarantee.
Instead the report builder takes the environment as an argument, passed by the
pipeline from `scope.env`, and writes it after the subject prefix on both
report shapes (`[prefix] [prod] …`) and into the body's first sentence. Putting
it in the subject rather than a new `TriageReport` field means every channel
shows it without a change to `notification`.

## Risks / Trade-offs

- **Changing `SCOPE_ENV` on a deployment with open incidents.** An open
  `checkout` incident recorded under prod would absorb staging alerts and be
  investigated as staging, because incidents are keyed by service. → Treat a
  changed environment as a new deployment with its own ledger, and say so in
  `docs/configuration.md`. Keying incidents by env would fix it properly and
  is left for the day a run watches more than one.
- **A service whose telemetry carries no `env` tag.** Its alerts vanish from
  the fetch and its metrics come back empty once specialists add `env:`. → The
  dialect already teaches that an empty answer is about the question, not the
  service; the instruction keeps that. The fetch side is the operator's to
  notice, and the documentation names it.
- **The environment tag might not be `env`.** Datadog's unified service tagging
  reserves `env`, so it is assumed. A deployment on another convention is out
  of reach until the tag is configurable.
- **Specialist instructions change.** Only the credential-gated live tests
  prove the queries still resolve; they are not run as part of this change.

## Migration Plan

None required. A deployment that sets nothing now watches `prod`, which
narrows what it fetched before. That is a behaviour change for any deployment
that was relying on alerts from other environments, and the release note must
say so.
