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

Hexagonal (ports & adapters). The domain doesn't know which alert source,
which multi-agent framework, or which notification channel it's talking
to — those are all adapters behind ports. This matters for two concrete
reasons: the tool is meant to be shared publicly so others can plug in
their own observability/notification tooling, and it needs to run in three
different execution contexts (manual/local, container, GKE/Cloud Run)
without the core changing.

One path is deliberately *not* a hand-written port: the evidence a
specialist agent gathers while investigating. That boundary is MCP itself.
The reasoning is in [Evidence and the platform
boundary](#evidence-and-the-platform-boundary) below, and it is a reversal
— slice 6 built the port, shipped it, and showed what extending it would
cost.

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
    └──────────────┘  └───────┬────────┘               └─────────────┘
                              │ MCP toolset, filtered per specialist,
                              │ every result through the evidence callback
                      ┌───────▼────────┐
                      │ Observability  │
                      │ MCP server     │
                      └────────────────┘
```

### Ports

- **AlertSource** — fetch recent alerts (Datadog REST adapter for v1, against
  the Events API). Ingestion asks one fixed question on a schedule and wants a
  typed answer with real pagination and errors that tell "no alerts" apart
  from "auth rejected". MCP earns its keep where a model discovers and
  chooses tools at runtime, which is the investigation path, not this one —
  and that path is reached through MCP directly rather than through a port
  of ours.
- **Investigator** — given a group of related alerts, produce findings +
  hypothesis (ADK multi-agent adapter for v1). This port stays: what the
  domain wants is "investigate this incident, give me findings", and that
  question is genuinely independent of who answers it.
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
agent that forms the actual hypothesis.

Each specialist is a **declaration**, not a construction: its name, the
signal it reports under, its instruction, its output schema, the toolsets
and tool names it may reach, and — optionally — the model it runs on. The
tools are part of the specialist's identity, since what an APM agent *is*
includes what it is allowed to ask. Changing them is editing one tuple
rather than threading an argument through the coordinator that runs the
crew. The composition root supplies only deployment facts: where the MCP
server is, how to authenticate, and the default model.

Two things that would otherwise be structural become cheap. A specialist
can name its own model, so trace-waterfall reasoning can run on a stronger
one than log pattern-spotting without either being a special case. And the
coordinator never learns a tool signature, so adding the remaining
specialists is adding declarations rather than editing the thing that runs
them.

The crew:

- **APM agent** — service-level golden signals (latency, error rate,
  throughput), plus single-hop upstream/downstream evidence (e.g. "latency
  degraded, correlates with a call-volume increase from upstream service
  X"). Deliberately bounded to one hop — it does not recursively
  investigate the neighboring services themselves. That's a roadmap item.
  On Datadog the dependency evidence is a tool rather than an inference:
  `search_datadog_service_dependencies`. Note that Grafana has no
  equivalent, which is one of the reasons the platform boundary moved —
  see below.
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

Deploy-version comparisons (item: "did this start after a deploy") need no
separate version-control integration for v1. Datadog answers the question
directly with `get_change_stories` / `semantic_search_change_stories`,
which return deployments and infrastructure changes over a window — a
better answer than reading the service-version tag, and one the specialist
reaches simply by listing the tool. Comparing against actual GitHub history
remains a roadmap item.

### Evidence and the platform boundary

Slice 6 shipped an `ObservabilityPlatform` port: one typed method per
question a specialist could ask, with a Datadog MCP adapter translating
each answer into a domain record. It worked. Building it is also what
showed it should not be extended, for three reasons, in the order they
bite.

**The catalogue is far larger than a port can track.** Datadog's MCP server
exposes 150+ tools across 20+ toolsets. The four planned specialists want
roughly fifteen between them — `analyze_datadog_logs`,
`search_datadog_service_dependencies`, `apm_latency_bottleneck_summary`,
`get_change_stories`, `search_datadog_k8s_resources`, and the rest. One
method cost ~245 lines of adapter, nearly all of it turning JSON into other
JSON. The volume is not the worst of it; the gate is. Widening what an
agent may ask becomes a port change plus an adapter method plus a domain
type plus tests, which prices every "what if the trace agent had this tool"
experiment out of reach. Investigation quality is precisely the thing that
has to be iterated on.

**A second platform cannot satisfy the port anyway.** Checked against
Grafana's MCP server rather than assumed. Every Grafana query tool takes a
datasource UID discovered at runtime — a step with no Datadog counterpart
and nowhere to hide inside an adapter. Grafana has no service-dependency
tool at all, so the single-hop dependency evidence this document scopes
into v1 would have no implementation behind it. And Grafana has primitives
Datadog lacks — `find_error_pattern_logs`, `find_slow_requests` — that a
Datadog-shaped port cannot express, so its own strengths would be
unreachable through our abstraction. The port's promise, that substituting
the platform leaves every agent unchanged, is not merely expensive to keep.
Against a real second platform it is false.

**The vocabulary was never neutral.** `LogRecord` carries timestamp, level,
message, and service, read out of Datadog's `status` and `service` fields.
A Loki stream is a label set and a line, with no guaranteed `service`
label. The port claimed this project's vocabulary; what it actually had was
Datadog's, untested against anything else.

So MCP *is* the boundary. It is already a cross-vendor protocol for
discovering and invoking tools, and wrapping it in a second, hand-written
abstraction bought a neutrality that did not survive contact with a second
vendor.

#### Keeping the evidence discipline without the port

The port was also where fabricated evidence was caught: every record passed
through the adapter, so citations could be checked against what the
platform really returned. That discipline is kept. It moves down one layer,
to ADK's `after_tool_callback`, which sees every tool result before the
model does and may replace it. Catching fabrication there is strictly more
general, because it works for tools nobody wrote a method for.

The citation unit generalises with it. Records-with-ids only works for
tools returning discrete records; aggregations, flame graphs, dependency
maps and trace waterfalls have no such thing, and those are among the most
useful tools available. So both the call and the items within it are
identified:

```
call-3           one tool call, its result held verbatim
call-3/item-7    one record within that result
```

A pattern finding cites items; an aggregate finding cites the call. A
finding citing neither is discarded, exactly as before.

Two things the port gave for free now have to be built deliberately:

- **A failed search must not read as silence.** `ObservabilityPlatformError`
  kept "the service logged nothing" apart from "the search failed", which
  are opposite findings. With a toolset, a failure comes back as an MCP
  error result that the *model* interprets — and it may well decide the
  service was quiet. The callback has to replace a failed result with an
  explicit refusal the model cannot misread, and record the failure so the
  investigation is reported as incomplete rather than empty. This is the
  one genuine regression, and it gates the restructure.
- **Evidence still has to render in an email.** With no per-tool domain
  type, one shallow normaliser gives every retrieved item an id, an
  instant, and a human-readable summary alongside its raw payload. One
  normaliser, not one per tool.

`before_tool_callback` is the matching seat on the way in, and it is where
the per-agent tool-call bound belongs — see [Circuit
breakers](#circuit-breakers).

#### What portability now means

Dropping the port does not drop the goal. It relocates it, and makes it
honest. What stays platform-neutral is the machinery: the evidence
callback, the output schemas, `Signal`, `Finding`, the report, the retry
arc, the ledger. What is platform-specific is the specialist itself — its
tool names and its instruction — because query dialects (Datadog's syntax,
LogQL, PromQL) are not translatable in any case, and the old port only
pretended otherwise by passing the dialect through a parameter labelled
neutral.

That is a smaller neutral core than the port claimed, and unlike the
port's, it is true. It also fits the actual goal better. Sharing this
publicly is a *contributor* story rather than a migration story, and the
two have opposite economics: a port asks a contributor to implement fifteen
methods before anything runs at all, whereas a declaration asks them to
copy one specialist, swap a tuple of tool names, and rewrite one
instruction — yielding a working Grafana logs specialist on its own,
without touching the rest. It also lets a platform contribute specialists
that have no counterpart elsewhere, rather than forcing every platform into
Datadog's shape.

What is lost is the completeness contract. A type checker could tell a
contributor when a port was fully implemented; nothing tells them whether
their instruction is any good. The answer to that is an evaluation harness,
not a port — canned incidents with expected findings, scored per
specialist. It is owed to the Datadog specialists just as much, which is
why it is now a slice of its own rather than a nicety.

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

Two of these defaults were set when a specialist had exactly one tool, and
the move to MCP toolsets changes what they mean:

- `max_tool_calls_per_agent` stops being a safety net and becomes a live
  constraint. A specialist with one tool could hardly loop; one with six
  and runtime discovery will, and on Grafana it must spend calls on
  datasource discovery before it can ask anything at all. The bound now
  belongs in `before_tool_callback`, which is a better seat than the old
  design had for it — the callback can refuse a call rather than the
  coordinator counting after the fact.
- `max_mcp_retries` and `mcp_call_timeout_seconds` were ours to enforce
  while we owned the MCP client. With `McpToolset`, ADK owns it, and the
  restructure decided both:
  - `mcp_call_timeout_seconds` is **re-expressed** through the toolset's
    connection parameters, whose `timeout` and `sse_read_timeout` are what
    now bound a call. Both are set explicitly beside the connection, so
    ADK's own defaults — five seconds to connect and five minutes to read —
    cannot apply by accident to a bound stated as thirty seconds. Reading
    them from config is slice 12's wiring.
  - `max_mcp_retries` is **superseded**. ADK's toolset already rebuilds a
    dead session and retries once, and there is no seam to make that count
    configurable short of reimplementing the toolset. Slice 12 removes the
    key rather than leaving an operator setting that does nothing.

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
- `investigation` — optional. How an investigation reasons and how many
  chances it gets: `model` (the default every specialist runs on) and
  `max_attempts` (how many investigations one incident may be given in
  total, first included, default three — one disables retrying). Because a
  specialist is a named declaration, `model` can be overridden per
  specialist without a schema change:

  ```yaml
  investigation:
    model: gemini-2.5-flash        # the default for every specialist
    specialists:
      trace:
        model: gemini-2.5-pro      # waterfall reasoning wants more
  ```

  The credential the model needs is *not* here — it is a deployment fact,
  read from the environment like every other. Which tools a specialist may
  reach is not here either: that is the specialist's identity, expressed in
  code beside its instruction, not an operator setting. An operator tuning
  tool lists at runtime would be editing the agent's job description
  through a config file, and the instruction that assumes those tools would
  not follow.
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
- `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) — the credential an investigation's
  model reasons on, under the Google GenAI SDK's own names so an operator
  who already exports one exports nothing new. No default. A deployment
  authenticating against the enterprise platform sets
  `GOOGLE_GENAI_USE_ENTERPRISE` instead, and is not refused for having no
  API key; `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` name where its
  investigations are billed and made, and fall back to what that platform's
  own credential discovery provides. Which model runs is
  behavior and lives in `config.yaml`; the key it costs to reach is a
  deployment fact and lives here.

  These are *resolved and supplied to the model*, not left for the SDK to
  rediscover. The SDK reads the process environment; a run reads the process
  environment supplemented by its `.env`, and a name the file supplies is one
  the SDK would never see. Supplying it is also what makes the refusal
  trustworthy: the value the run refuses on is the value the model is built
  from, so a deployment cannot pass its startup check and then fail to
  authenticate on the first incident.

  The one name this does not cover is `GOOGLE_APPLICATION_CREDENTIALS`, read
  by the Google auth library from the process environment before any of this
  is resolved. A service-account path belongs in the process environment, not
  in `.env`.
- `ALERT_TRIAGE_LEDGER_PATH` — where the triage ledger keeps its records,
  defaulting to `data/alert_triage.db` under the working directory. Unlike a
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

- FinOps agent (cost-impact or cost-anomaly investigation). Datadog's
  `cost_recommendations` makes this a specialist declaration rather than an
  integration, which lowers its cost considerably.
- Multi-hop dependency traversal (recursively investigating upstream/
  downstream services, not just single-hop evidence)
- GitHub deploy-history correlation. Less urgent than it was: Datadog's
  change-story tools already answer "did this start after a deploy" without
  leaving the platform, so this is now about correlating with commits and
  authors rather than about detecting the deploy at all.
- A second observability platform (Grafana is the obvious candidate). What
  it takes is set out under [What portability now
  means](#what-portability-now-means): specialists of its own, not an
  adapter implementing ours.

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
  inbound channel — it is another read through a boundary that already
  exists — and it respects where people already work. Probably the first
  thing to try, and cheaper than it looked: `search_datadog_monitors`
  returns monitors by status, and Grafana OnCall's `update_alert_group`
  acknowledges and resolves outright. Reaching either is adding a tool name
  to a declaration, not building an integration.
- **From the notification channel.** A reaction or reply on the Teams message,
  a reply to the email. Closest to where the report is actually read, but the
  `Notifier` port is one-way by design, and acknowledgement is inbound.
  Polling for reactions keeps the scheduled-job shape; a webhook does not —
  it turns a job that runs and exits into a service that must be reachable,
  which is a deployment change (slice 14), not just a port.

Two failure modes worth designing against from the start:

- **An acknowledgement that never expires is a mute button.** "I'm on it" said
  on Monday should not silence Thursday's report about the same service. An
  ack wants a bounded life — a snooze with a duration, or one that lapses
  when the incident closes — so that going quiet is always a decision
  someone made recently.
- **A worsening incident must break through.** Acknowledgement suppresses the
  routine repeat, not the escalation path (slice 11). If severity crosses a
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
   agent (Logs)** — *done, and partly superseded.* It proved the ADK + MCP
   pattern, the evidence discipline, and the retry arc, all of which stand.
   It also established that the `ObservabilityPlatform` port should not be
   extended — see [Evidence and the platform
   boundary](#evidence-and-the-platform-boundary). Its live-MCP test and
   README tasks were deliberately left undone rather than written against
   an architecture already being replaced.
7. **Investigation restructure** — retire the `ObservabilityPlatform` port
   in favour of a filtered MCP toolset per specialist; move the evidence
   check into `after_tool_callback` and generalise citations to
   call-and-item; make each specialist a named declaration owning its
   tools, instruction, schema, and optional model. Ordered first because
   every later investigation slice is cheaper after it and rework without
   it compounds. Its gate is the failed-search-is-not-silence marker: until
   a failed search demonstrably cannot be read as a quiet service, the
   restructure is not done. Testable with a stubbed model and a fake MCP
   server, plus the first credential-gated live run.
8. **Evaluation harness** — canned incidents with expected findings, scored
   per specialist, so instruction quality is measurable rather than felt.
   Ordered before the remaining specialists deliberately: the restructure
   makes the instruction the main variable, and writing three more of them
   blind is how you end up with three that need rewriting. It also settles
   the questions slice 6 left open — which model to default to, and how
   many examples a finding should carry. Testable as a scoring run over
   fixtures.
9. **Remaining specialist agents** (APM incl. single-hop dependency
   evidence, Trace, Infrastructure) — one declaration each, added
   independently, scored by slice 8.
10. **Diagnostician + Report agent** — cross-signal reasoning to hypothesis
    + confidence, then formatting. Testable against canned findings.
11. **Escalation path** — severity/threshold rule + critical-services
    overrides, bypassing batching. Testable as rule-engine unit tests.
12. **Circuit breakers** — per-agent, per-hop, and per-investigation bounds;
    trip → partial report + auto-escalate. The per-agent bound sits in
    `before_tool_callback`, and the two MCP-level bounds are re-expressed
    through ADK's connection parameters. Testable by forcing a trip
    condition.
13. **CI gate failure-mode confirmation** — the leftover of slice 0: push a
    deliberate lint error, a type error, and a boundary violation on a scratch
    branch and confirm each produces a red run naming the rule, the expression,
    and the offending import, then delete the branch. Deferred out of slice 0
    because it is the one check that cannot be proven locally — it needs real
    runs on the remote. Criteria VLD-002…VLD-004 in
    `docs/spec-process-cicd-ci.md`.
14. **Deployment packaging** — containerize, then Cloud Run/GKE manifests.
    Testable via container build + smoke test.
15. **README architecture diagram rework** — the diagram the bounded-context
    restructure left behind states the shape correctly and reads poorly: four
    nested subgraphs, an enclosing box for configuration, and a rung per layer
    inside each context, all competing for the same glance. Deliberately last,
    because every slice before it changes what the picture has to say. Slice 10
    moves report formatting into an agent, which dissolves triage's deep read
    of investigation's vocabulary and so redraws one of the two cross-context
    edges. Slice 11 adds a path that bypasses batching entirely, which the
    current picture has nowhere to put. Slice 14 introduces a deployment story
    a reader will want to see and there is no version of that in it today.
    Redrawing before those land is redrawing twice, and a diagram is the one
    artefact where being out of date is worse than being ugly.

    Likely more than one picture rather than a better single one: what the
    contexts are and how they depend on each other is a different question from
    what happens to one alert on its way to a report, and today's diagram
    answers the first while most readers arrive wanting the second. Worth
    settling then, not now. Regenerated through the mermaid MCP tool per the
    conventions above; the acceptance is a reader who has not seen the codebase
    reaching the right mental model unaided, which is a judgement rather than a
    test, so it does not gate a green build.
