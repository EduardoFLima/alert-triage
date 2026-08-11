# Vision: Alert Triage

## Problem

Teams receive Datadog alerts and ignore them. Not because the alerts are
wrong, but because responding requires time and troubleshooting knowledge
most people don't have in the moment. The result: real signal gets lost in
the noise of things nobody has time to investigate.

## What this builds

A recurring job that watches for recent Datadog alerts, does the first-pass
investigation a knowledgeable human would do if they had the time, and sends
a triage report to the team — so the decision left to a human is "act on
this" rather than "figure out where to even start."

It explicitly does **not** try to auto-remediate or decide for the human. It
does the legwork and presents a hypothesis with its confidence, not a verdict.

## Architecture

Hexagonal (ports & adapters). The domain doesn't know which observability
tool, which multi-agent framework, or which notification channel it's
talking to — those are all adapters behind ports. This matters for two
concrete reasons: the tool is meant to be shared publicly so others can
plug in their own observability/notification tooling, and it needs to run
in three different execution contexts (manual/local, container, GKE/Cloud
Run) without the core changing.

```
┌───────────────────────────────────────────────────────────────────┐
│                          Core Domain                                │
│                                                                     │
│  Alert ──▶ Grouper ──▶ Investigator ──▶ Diagnostician ──▶ Report    │
│              │              │                                │      │
│              ▼              │                                ▼      │
│        TriageLedger ◀───────┘                            Escalator  │
│        (dedup/cooldown)                              (side-channel) │
└───────────┬─────────────────┬───────────────────────────────┬──────┘
            │                 │                                │
    ┌───────▼──────┐  ┌───────▼────────┐               ┌──────▼──────┐
    │ AlertSource  │  │ Investigator   │               │ Notifier    │
    │ port         │  │ port           │               │ port        │
    └───────┬──────┘  └───────┬────────┘               └──────┬──────┘
    ┌───────▼──────┐  ┌───────▼────────┐               ┌──────▼──────┐
    │ Datadog      │  │ ADK agent crew │               │ Email       │
    │ REST adapter │  │ adapter        │               │ Teams       │
    └──────────────┘  └────────────────┘               └─────────────┘
```

### Ports

- **AlertSource** — fetch recent alerts (Datadog REST adapter for v1, against
  the Events API). Ingestion asks one fixed question on a schedule and wants a
  typed answer with real pagination and errors that tell "no alerts" apart
  from "auth rejected"; MCP earns its keep where a model discovers and
  chooses tools at runtime, which is the `ObservabilityPlatform` port below,
  not this one.
- **Investigator** — given a group of related alerts, produce findings +
  hypothesis (ADK multi-agent adapter for v1)
- **ObservabilityPlatform** — queried by the investigator's specialist
  agents for logs, traces, and metrics around the alert window (Datadog
  MCP adapter for v1)
- **TriageLedger** — tracks which alert-groups have already been reported
  and when, to dedup and enforce re-notify cooldown
- **Notifier** — deliver the triage report (Email + Teams adapters for v1)
- **Config** — optional YAML, provides critical-services registry,
  circuit-breaker thresholds, and room to grow other settings later.
  Absence of the file means sensible defaults apply everywhere.

### Grouping

Alerts are grouped as "the same incident" when they share a service tag and
fall within the same time window. A group is investigated and reported
once, not per-alert.

### Investigation — multi-agent (Google ADK, Python)

The Investigator is one adapter implementation: a crew of specialist
agents, each scoped to one observability dimension, feeding a reasoning
agent that forms the actual hypothesis:

- **APM agent** — service-level golden signals (latency, error rate,
  throughput), plus single-hop upstream/downstream evidence (e.g. "latency
  degraded, correlates with a call-volume increase from upstream service
  X"). Deliberately bounded to one hop — it does not recursively
  investigate the neighboring services themselves. That's a roadmap item.
- **Trace agent** — specific slow/failed trace waterfall analysis
- **Logs agent** — error/warning patterns around the alert window
- **Infrastructure agent** — CPU/memory/disk/network around the alert
  window
- **Diagnostician agent** — reasons across all the above, produces a
  hypothesis with an explicit confidence level. Kept separate from Report
  so that reasoning quality and message formatting can be tuned
  independently.
- **Report agent** — formats the Diagnostician's hypothesis + evidence into
  the actual email/Teams message

Deploy-version comparisons (item: "did this start after a deploy") use
Datadog's own service-version tag — no separate version-control integration
needed for v1. Comparing against actual GitHub history is a roadmap item.

### Re-notification

Configurable cooldown before re-reporting an alert-group that's still
firing or has re-fired; defaults to 2 days. The key is
`re_notify.cooldown_seconds` in `config.yaml`, or `RE_NOTIFY_COOLDOWN_SECONDS`
in the environment.

The cooldown is counted per incident from its most recent report, not per
service and not from the first one: a second, unrelated incident on a service
inside another's cooldown is still reported.

The cooldown is currently the *only* thing standing between a still-firing
incident and another report. The system knows what it has told the team and
when; it does not know whether anyone read it, or is already working on it. A
team that reacted to the first report gets told again every cooldown for as
long as the alerts keep firing — which is the alert fatigue this project
exists to reduce, reintroduced one layer up. Acknowledgement is the missing
control; see the roadmap entry below.

### Triage history

An incident **closes** once it can no longer affect a decision — its latest
alert is older than the grouping window *and* its last report is older than
the cooldown. Closing needs no setting of its own, since both bounds already
exist, and the moment it happens is stamped rather than recomputed, so
retuning either bound later cannot move a closure that already happened.

A closed record is kept for `ledger.retention_seconds`
(`LEDGER_RETENTION_SECONDS`), defaulting to 30 days, so a human can go back
and see what was reported, when, and for which alerts; after that it is
deleted, which is what bounds the ledger's growth. Retention is deliberately
its own setting rather than a bound derived from the cooldown: how long
history is kept and how often a report repeats answer different questions.
The two compose rather than compete no matter how they are set, because
retention is measured from the moment an incident closes and closing already
requires the cooldown to have elapsed.

### Escalation

A severity/threshold rule (e.g. latency above a defined threshold), with
per-service overrides from the critical-services config, bypasses batching
entirely and notifies immediately — a "needs a human now" path that doesn't
wait on investigation or digest cadence.

### Circuit breakers

Multi-agent investigation can loop or run away in three distinct ways:
within one agent's tool-calling loop, across agents handing off to each
other, or just running long. Each is bounded independently, configurable in
the same optional YAML, with defaults:

| Breaker | Default |
|---|---|
| `max_tool_calls_per_agent` | 8 |
| `max_agent_hops` | 2 |
| `max_investigation_duration_seconds` | 300 |
| `max_mcp_retries` | 3 |
| `mcp_call_timeout_seconds` | 30 |

A tripped breaker does not silently truncate: it produces a report marked
"investigation incomplete" with whatever partial evidence was gathered, and
routes through the escalation path — an incomplete automated triage is
itself a signal a human should look sooner.

## Config file

A single YAML file (e.g. `config.yaml`) is the one place configuration is
described. The file's existence is still optional — but the `scope` value
it (or an environment variable) provides is not:

- `scope.owner` — **mandatory value, from either source.** For v1, a single
  team: the job watches only alerts belonging to that owner. It can
  be set in `config.yaml`, or via an environment variable (see below), or
  both — if both are set, the environment variable wins. It must resolve
  from one of the two. No default, no "watch
  everything" fallback: if neither `config.yaml` nor the environment
  provides it, the application refuses to start. The name is deliberately
  platform-neutral: turning the owner into a `team:` term in a Datadog query
  is the alert source adapter's job, so a second platform reads the same key
  without it lying about where the value came from. Widening scope beyond a
  single team (multiple teams, tag-based scoping, etc.) is a future
  extension, not v1.
- `critical_services` — optional, service → criticality tier → custom
  thresholds. Defaults apply if absent.
- `circuit_breakers` — optional, the thresholds listed above. Defaults
  apply if absent.
- `ingestion` — optional. How far back a run looks for alerts
  (`lookback_seconds`, default one hour) and the bounds a fetch runs under
  (`request_timeout_seconds`, `max_retries`). These are ingestion's own
  settings, resolved independently of the `circuit_breakers` above: those
  bound an agent's tool calls during investigation, and the two will be
  tuned against different evidence.
- `re_notify` — optional. How long a report suppresses the next one for the
  same incident (`cooldown_seconds`, default 2 days).
- `ledger` — optional. How long a closed incident is kept for a human to
  consult before it is deleted (`retention_seconds`, default 30 days).
  Resolved independently of `re_notify`: neither value is derived from the
  other. Where the ledger keeps its records is *not* here — a storage
  location is a deployment fact, read from the environment.
- room to grow other behavior settings later without a schema rewrite

So `config.yaml` as a file is never required to exist — a deployment could
supply scope purely through environment variables and skip the file
entirely — but the *value* of `scope` is always required at startup,
regardless of which source supplies it.

### Environment variable overrides

Any value normally set in `config.yaml` can instead be set via an
environment variable, following a predictable naming convention (e.g. a
section/key path mapped to `SCREAMING_SNAKE_CASE`, such as
`SCOPE_OWNER` for `scope.owner`). When both are present, the
environment variable always takes precedence over the YAML value — this
holds for every config value, not just `scope`. This is how `scope` can be
satisfied without a config file at all, and matters most for deploy
targets beyond manual/local: containers and GKE/Cloud Run jobs configure
per-environment values (or one-off overrides) through env vars rather than
baking per-team YAML files into images.

The override runs one way only. Every *behavior* value has an environment
equivalent, but some settings live in the environment exclusively and have no
`config.yaml` key at all — see below.

### Behavior belongs in the file; connections belong in the environment

`config.yaml` answers "how should the system triage": what it watches, how it
groups, how far back it looks, when it escalates. It does not answer "where is
the platform and how do I authenticate". Sites, regions, endpoints, hostnames,
and credentials are deployment facts — they change when the same behavior is
pointed at a different account — and they are read from the environment only,
under the platform's own conventional variable names rather than the
`section.key` mapping above:

- `DD_API_KEY`, `DD_APP_KEY` — Datadog credentials. No default; the
  application refuses to start without them.
- `DD_SITE` — Datadog region, defaulting to `datadoghq.com`.
- `ALERT_TRIAGE_LEDGER_PATH` — where the triage ledger keeps its records,
  defaulting to `alert_triage.db` in the working directory. Unlike a
  credential it has a default, because a path is not a secret and a manual run
  should need no configuration beyond `scope`.

Written into `config.yaml`, such a key is inert: it is not used to reach the
platform, and resolution proceeds as if it were absent. This keeps a config
file portable across deployments and means there is never a key shaped like a
credential for someone to fill in and commit. The same test decides where a
new setting goes — the notifier's SMTP host and Teams webhook land on the
environment side by it.

## Deployment

v1 runs manually, from a developer's machine. Next step: containerize so
the same image can run for different teams' configs. After that: deploy to
GCP (Cloud Run job or GKE) — GCP is the target landscape.

## Repo & engineering conventions

- **AGENTS.md is canonical.** Other harness-specific filenames (e.g.
  `CLAUDE.md`) are symlinks to it — no duplicated instructions across
  harnesses.
- **AGENTS.md holds practices, not product knowledge.** It should never
  duplicate what's in the README; if a coding agent needs to understand
  what the application does, it reads the README, not AGENTS.md.
- **AGENTS.md mandates**: clean code, TDD (red/green/refactor), clean
  (hexagonal) architecture — the same architecture described above, kept
  intact as the codebase grows. Also: use context7 to look up current
  library/framework docs rather than relying on training data (ADK, MCP,
  and friends move fast); use a mermaid MCP tool for any diagrams added to
  the README, rather than hand-rolled ASCII or static images.
- **README** carries setup instructions, the architecture diagram (kept in
  sync via mermaid), and a guide for adding a new observability or
  notification adapter — since sharing this publicly for others to extend
  is an explicit goal.
- **Tests** are expected throughout, practiced as TDD rather than added
  after the fact.

## Explicitly deferred (roadmap, not v1 scope)

- FinOps agent (cost-impact or cost-anomaly investigation)
- Multi-hop dependency traversal (recursively investigating upstream/
  downstream services, not just single-hop evidence)
- GitHub deploy-history correlation (beyond the DD version tag)

### Acknowledgement — the missing input

v1 models one half of the conversation. The ledger records what was reported
and when, so triage can ask "have we said this recently?" — but never "did
anyone act on it?". Those are different questions, and answering only the
first means a team that already picked up an incident is told about it again
every cooldown until the alerts stop.

Today's states are effectively *reported* and *quiet*. Three are needed:

- **reported, unseen** — the current re-notify behavior is right here.
- **acknowledged** — a human has it. Reporting pauses; tracking does not. The
  incident stays open, keeps absorbing alerts, and keeps its record, because
  an acknowledged incident is still an incident.
- **resolved** — the problem is over. Distinct from the *inferred* closure
  this slice implements, which reads silence as resolution. Silence is
  evidence, not proof: a monitor that recovers says so explicitly, and a
  report worth sending is one that can say "this is fixed" rather than
  leaving a human to notice nothing arrived.

The incident identity added in slice 3 is what makes this tractable — an
acknowledgement needs something stable to attach to, and a generated id that
survives new alerts joining is exactly that. Storage is a column beside
`last_reported_at`, not a redesign.

The hard part is where the signal comes from, and it is an architectural
question rather than a feature:

- **From the observability platform.** Datadog monitors already carry ack and
  mute state, and a team that acts usually acts there first. This needs no new
  inbound channel — it is another read through the ports that already
  exist — and it respects where people already work. Probably the first
  thing to try.
- **From the notification channel.** A reaction or reply on the Teams message,
  a reply to the email. Closest to where the report is actually read, but the
  `Notifier` port is one-way by design, and acknowledgement is inbound.
  Polling for reactions keeps the scheduled-job shape; a webhook does not —
  it turns a job that runs and exits into a service that must be reachable,
  which is a deployment change (slice 12), not just a port.

Two failure modes worth designing against from the start:

- **An acknowledgement that never expires is a mute button.** "I'm on it" said
  on Monday should not silence Thursday's report about the same service. An
  ack wants a bounded life — a snooze with a duration, or one that lapses
  when the incident closes — so that going quiet is always a decision
  someone made recently.
- **A worsening incident must break through.** Acknowledgement suppresses the
  routine repeat, not the escalation path (slice 9). If severity crosses a
  threshold or the blast radius grows, that is new information and the ack
  should not hold it back.

## Capability slices (dependency order)

Each slice is a vertical cut: independently buildable and independently
testable, building only on the slices before it.

0. **Scaffolding & conventions** — AGENTS.md (+ symlinks), README skeleton,
   hexagonal folder layout, test harness. Testable via repo structure/CI
   skeleton.
1. **Core domain & config** — Alert entity, grouping logic, Config port +
   YAML loader with defaults for optional sections, mandatory `scope`
   (v1: Datadog team) with no fallback if missing, and environment
   variable overrides for any config value. Testable as pure unit tests.
2. **Alert ingestion** — AlertSource port + Datadog REST adapter over the
   Events API. Testable against canned event payloads, with no network.
3. **TriageLedger** — dedup/cooldown persistence, kept in SQLite over the
   standard library's `sqlite3`: durable across processes, transactional, and
   one file to move or delete, which adds no dependency and keeps the core
   free of one. The decision itself — continuation, and report versus
   suppress — stays in the domain; the port only stores. Testable in
   isolation with a fake clock.
4. **Notification** — Notifier port + Email + Teams adapters, sending stub
   content. Testable independently of investigation.
5. **End-to-end skeleton** — wires ingestion → grouping → ledger → notifier
   with a trivial pass-through report; first fully runnable manual job.
   Testable end-to-end with fakes.
6. **Investigator port + ObservabilityPlatform port + first specialist
   agent (Logs)** — proves the ADK + MCP adapter pattern, with the Logs
   agent querying observability data through the ObservabilityPlatform
   port. Testable against mocked MCP tool responses.
7. **Remaining specialist agents** (APM incl. single-hop dependency
   evidence, Trace, Infrastructure) — same pattern as slice 6, querying
   through the same ObservabilityPlatform port, addable independently.
8. **Diagnostician + Report agent** — cross-signal reasoning to hypothesis
   + confidence, then formatting. Testable against canned findings.
9. **Escalation path** — severity/threshold rule + critical-services
   overrides, bypassing batching. Testable as rule-engine unit tests.
10. **Circuit breakers** — per-agent, per-hop, and per-investigation bounds;
    trip → partial report + auto-escalate. Testable by forcing a trip
    condition.
11. **CI gate failure-mode confirmation** — the leftover of slice 0: push a
    deliberate lint error, a type error, and a boundary violation on a scratch
    branch and confirm each produces a red run naming the rule, the expression,
    and the offending import, then delete the branch. Deferred out of slice 0
    because it is the one check that cannot be proven locally — it needs real
    runs on the remote. Criteria VLD-002…VLD-004 in
    `docs/spec-process-cicd-ci.md`.
12. **Deployment packaging** — containerize, then Cloud Run/GKE manifests.
    Testable via container build + smoke test.
