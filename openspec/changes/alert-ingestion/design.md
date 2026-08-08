## Context

See proposal.md - Why. Slice 1 left a domain that can group alerts and a
`Config` port resolved from YAML and environment; `adapters/datadog/` exists as
an empty placeholder. This slice adds the first adapter that performs real
I/O, which makes it the place several conventions get set for the first time:
how a vendor client is constructed and injected, how vendor errors are
translated at the boundary, and how the circuit-breaker values already sitting
in the `Config` port get honoured.

The one constraint worth naming up front: `docs/vision.md` assigns a Datadog
MCP adapter to this port. That is being changed here (proposal.md - Why), and
the vision doc is edited as part of the change rather than left contradicting
the code.

## Goals / Non-Goals

**Goals:**
- Keep the `AlertSource` port expressible by a non-Datadog adapter — the
  publicly-shared-and-extensible goal in `docs/vision.md` is only real if the
  port's shape does not encode one platform's query model.
- Set the boundary-translation pattern (vendor exception in, project exception
  out) that every later adapter follows.
- Make the adapter fully testable without network, so ingestion tests live in
  `tests/unit/` rather than only in `tests/integration/`.

**Non-Goals:**
- Choosing how often the job runs, or the scheduler that runs it — the port
  takes the time bound as an argument and the app supplies it (slice 5, then
  slice 12).
- Wiring the circuit breakers to investigation logic; only the two transport
  values (`mcp_call_timeout_seconds`, `max_mcp_retries`) are consumed here.
  The rest stay unused until slice 10.
- Deciding what happens to alerts once fetched — dedup is slice 3, delivery is
  slice 4.
- Any MCP integration. MCP arrives with the `ObservabilityPlatform` port in
  slice 6, where an LLM agent is the consumer.

## Decisions

**REST API for this port, MCP for `ObservabilityPlatform`.**
MCP's value is letting a model discover tools and choose among them at
runtime; its results are shaped for a model to read. Ingestion asks one fixed
question on a schedule and wants a typed answer, real pagination, and errors
that distinguish "no alerts" from "auth rejected" — all of which the REST API
gives directly and MCP gives only after parsing a tool result. The specialist
agents in slice 6 have the opposite profile and keep MCP. Alternative
considered: MCP for both, as `docs/vision.md` originally specified — rejected
because it buys uniformity of transport at the cost of determinism in the one
component that has no model in the loop.

**Datadog's Events API v2 search endpoint, not the Monitors API.**
`POST /api/v2/events/search` takes a query, a `from`/`to` range, and a cursor,
and returns *firing events with timestamps* — which is exactly the shape
`Alert(service, fired_at, ...)` needs. The Monitors API returns a monitor's
*current* overall state, from which "when did this fire" cannot be recovered
for a lookback window. Scope becomes a term in the event query
(`team:<scope.owner>` alongside a monitor-alert source filter) rather
than client-side filtering, so paging is not spent on out-of-scope events.

**A synchronous port.** `datadog-api-client` is a blocking client, and this
slice has no concurrency to exploit — one paginated fetch per run. Declaring
the port `async` would push an event loop into the composition root to serve a
component that does not need one. Alternative considered: async everywhere for
consistency with the ADK adapter landing in slice 6 — rejected because ports
are independent, and the async boundary belongs where the async library
actually is. If a future adapter needs concurrency, it owns a thread or a loop
internally without changing the port.

**The client is injected, not constructed inside the adapter.** The adapter
takes an already-configured API client. This is what lets the unit tests hand
it a fake returning canned page payloads and assert on translation,
pagination, exclusion, and error mapping with no network and no vendor
plumbing — and it keeps credential and site resolution in the composition root
where the `Config` port already lives. Alternative considered: the adapter
builds its own client from a `Config`; rejected because it makes the adapter
untestable without either network or monkeypatching, and drags config
knowledge into a component whose job is translation.

**Vendor exceptions are translated at the adapter boundary into a project
exception defined beside the port.** `AlertSourceError` sits next to the
`AlertSource` port, mirroring how `ConfigError` sits beside `Config`. Callers
handle "alerts could not be fetched" without importing anything Datadog. This
is what makes the "failed fetch is reported, not disguised" requirement
enforceable: there is exactly one error type to catch, and returning an empty
list on failure is visibly wrong.

**Ingestion gets its own timeout and retry settings, not the `mcp_*` breakers.**
Reusing `mcp_call_timeout_seconds` and `max_mcp_retries` here would be a pun on
a shared default value, not a shared concept: those bound an LLM agent's MCP
tool calls during investigation, this bounds one paginated REST fetch. The two
have different failure modes and will be tuned against different evidence — an
operator lengthening the agents' tool-call timeout because a logs query is slow
should not thereby make the alert fetch hang longer. Coupling them would also
tie this slice to slice 10's breaker surface, so any later rename or reshaping
of the breakers would ripple into ingestion. They live beside the lookback as
ingestion's own settings, with their own documented defaults. Alternative
considered: reuse the existing keys since they already exist and the numbers
would start out identical — rejected; equal defaults are not a reason to share
a knob.

**Timeout and retries are configured on the client, not hand-rolled.**
`datadog-api-client`'s `Configuration` exposes `enable_retry`, `max_retries`,
and a retry policy covering 429 and 5xx, plus a request timeout. Mapping
ingestion's two settings onto those is less code and better behaviour
(backoff, correct status handling) than a bespoke retry loop.

**`config.yaml` is behavior; connection settings are environment-only.**
The file answers "how should the system triage" — what it watches, how it
groups, how far back it looks, when it escalates. It deliberately does not
answer "where is the platform and how do I authenticate": site, region, and
credentials are deployment facts that change when the same behavior is pointed
at a different account, and the container and Cloud Run targets in
`docs/vision.md` configure exactly those through env vars. Keeping them out of
the file entirely — rather than in it with an env override — means a config
file is portable across deployments, and there is no key shaped like a
credential for someone to fill in and commit. This generalises the
credentials-are-secrets rule into a boundary later slices can apply without
re-litigating it: the notifier's SMTP host and Teams webhook (slice 4) land on
the environment side by the same test. Alternative considered: allow site in
YAML with the usual env-wins precedence, consistent with every other value —
rejected because "consistent with other config values" is the wrong axis; the
useful distinction is behavior versus deployment, and blurring it is how
`config.yaml` accretes endpoints and eventually secrets.

**`scope` names an owner, not a Datadog team.** The scope setting stays in
`config.yaml` — it selects *which alerts are triaged*, which is behavior — but
it is renamed `scope.owner`. Two separate tests apply to a setting and they
were being conflated: *behavior vs. deployment* decides which side of the
config/environment line it sits on, and *domain vocabulary vs. vendor
vocabulary* decides what it is called. `scope.datadog_team` passed the first
and failed the second. The value is a plain owner identifier; the fact that
this adapter spends it as a `team:` term in an event query is a Datadog
encoding, and belongs in the adapter next to the `service:` tag parsing that
is already there for the same reason. Leaving the vendor name in place would
mean a future PagerDuty or Opsgenie source either reads a key called
`datadog_team` or the port grows a second field for the same concept.
Alternative considered: `scope.team`, which is also platform-neutral and more
concrete — `owner` was chosen because the vision's own roadmap contemplates
widening scope beyond a single team, and `owner` accommodates a squad or a
service owner without a second rename.

**Service tag resolution lives in the adapter.** Datadog carries the service
on the event's tag list as `service:<name>`, which is a Datadog encoding, not
a domain concept. The adapter extracts it; the domain never sees a tag list.
Events with no such tag are dropped per the spec, since a group is keyed on
service and an alert without one cannot be grouped or reported against
anything.

## Risks / Trade-offs

- [Dropping alerts with no service tag is silent — a misconfigured monitor
  could have its alerts vanish with no trace] → Accepted for this slice: there
  is no logging port yet and inventing one here widens the slice. The adapter
  keeps the exclusion in one identifiable place so it can emit a count once
  observability of the job itself exists (slice 5's runnable job is the
  natural home).
- [Ingestion's bounds and the investigation breakers start with identical
  default values, which invites someone to later "deduplicate" them back into
  one setting] → The spec pins them as independently resolved, with scenarios
  asserting that changing one leaves the other unchanged, so a merge breaks a
  test rather than passing review.
- [Deriving `since` from a fixed lookback means a run that is skipped, delayed,
  or slower than the lookback silently misses alerts] → Accepted for v1: the
  default lookback is set comfortably wider than the intended run interval, and
  the TriageLedger in slice 3 makes overlapping windows safe by deduping
  re-seen groups. Tracking a real high-water mark belongs with the ledger's
  persistence, not here.
- [Adding `datadog-api-client` puts a large vendor SDK in the dependency tree
  and within reach of an accidental domain import] → Add it to the
  `forbidden_modules` list of the "Domain and ports are free of vendor
  libraries" contract in the same commit that adds the dependency, so the
  architecture test fails on the first stray import.
- [The Events API's event schema for monitor alerts is not fully pinned down
  from the docs alone] → The unit tests are written against canned payloads,
  so a wrong field assumption shows up as a translation test to fix rather
  than as a design change; an integration test against a real credential
  confirms the payload shape before the slice is called done.
