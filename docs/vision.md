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

Four bounded contexts, each a hexagon of its own. Inside a context,
dependencies point inward — adapters to ports to domain. Between contexts,
what one offers another is a published contract and everything behind it is
private. The domain doesn't know which alert source, which multi-agent
framework, or which notification channel it's talking to — those are all
adapters behind ports. This matters for two concrete reasons: the tool is
meant to be shared publicly so others can plug in their own
observability/notification tooling, and it needs to run in three different
execution environments (manual/local, container, GKE/Cloud Run) without the
core changing.

**Triage** is the core: it owns the incident, groups the alerts, and decides
what is owed about it. **Investigation** and **notification** are supporting
contexts, each reached only through the contract it publishes — a target goes
into one and findings come out; a report goes into the other and is delivered.
**Configuration** is a generic subdomain every context may depend on directly.
`shared/` holds vocabulary more than one context speaks and depends on no
context, which is what stops it becoming a dumping ground.

Triage is the customer of both supporting contexts and conforms to the
language each publishes, rather than translating it: an `InvestigationTarget`
is investigation's word for what it can be asked, and a `TriageReport` is
notification's word for what it can deliver. Two anticorruption layers keep
that one-directional — investigation never learns what an incident is, and
notification knows nothing of incidents or investigations.

One path is deliberately *not* a hand-written port: the evidence a
specialist agent gathers while investigating. That boundary is MCP itself.
The reasoning is in [Evidence and the platform
boundary](#evidence-and-the-platform-boundary) below, and it is a reversal
— slice 6 built the port, shipped it, and showed what extending it would
cost.

```
            app — composition root, the only place adapters are named
                  │
┌─────────────────▼────────────────────────────────────────────────────────┐
│ TRIAGE — the core context                                                │
│   domain    Alert ─▶ Grouping ─▶ Incident ─▶ Policy ─▶ Report            │
│   ports     AlertSource · TriageLedger                                   │
│   adapters  Datadog Events API · SQLite                                  │
└─────────────────┬──────────────────────────────────────┬─────────────────┘
                  │ asks                                 │ publishes
┌─────────────────▼─────────────────┐  ┌─────────────────▼─────────────────┐
│ INVESTIGATION — supporting        │  │ NOTIFICATION — supporting         │
│   contract  InvestigationTarget   │  │   contract  TriageReport          │
│             Findings              │  │                                   │
│   ports     Investigator          │  │   ports     Notifier              │
│   domain    Specialist · evidence │  │   adapters  Email · Teams         │
│   adapters  adk · datadog         │  │                                   │
└─────────────────┬─────────────────┘  └───────────────────────────────────┘
                  │ MCP toolset, filtered per specialist,
                  │ every result through the evidence callback
          ┌───────▼────────┐
          │ Observability  │
          │ MCP server     │
          └────────────────┘

configuration  every context may depend on it — YAML, then env over it
shared         Window; depends on no context
```

### Ports

A port is declared in the context whose own adapter implements it, so a port
and the things that answer it are found together. A context that sits on
neither end of a port has no claim on it — which is why `Investigator` belongs
to investigation even though only the composition root calls through it.

In triage:

- **AlertSource** — fetch recent alerts (Datadog REST adapter for v1, against
  the Events API). Ingestion asks one fixed question on a schedule and wants a
  typed answer with real pagination and errors that tell "no alerts" apart
  from "auth rejected". MCP earns its keep where a model discovers and
  chooses tools at runtime, which is the investigation path, not this one —
  and that path is reached through MCP directly rather than through a port
  of ours.
- **TriageLedger** — tracks which incidents have already been reported
  and when, to dedup and enforce re-notify cooldown

In investigation:

- **Investigator** — given a target, produce findings (ADK multi-agent adapter
  for v1). This port stays: what a caller wants is "investigate this, give me
  findings", and that question is genuinely independent of who answers it. It
  takes an `InvestigationTarget` rather than an incident — a service, a window,
  and how much fired in it — because an incident is triage's own aggregate and
  a contributor writing a specialist should not have to meet it.

In notification:

- **Notifier** — deliver the triage report (Email + Teams adapters for v1).
  One-way by design, which is what makes acknowledgement an architectural
  question rather than a method — see the roadmap entry below.

Configuration is a generic subdomain rather than a context with a contract, so
its **Config** port is reachable from every context directly: optional YAML,
providing the critical-services registry, circuit-breaker thresholds, and room
to grow other settings later. Absence of the file means sensible defaults apply
everywhere.

The observability platform has no port at all — MCP is already one. The
reasoning is under [Evidence and the platform
boundary](#evidence-and-the-platform-boundary).

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
- **Diagnostician agent** — decides which of the above an incident actually
  needs, reasons across what they report, and produces a hypothesis with an
  explicit confidence level. Kept separate from Report so that reasoning
  quality and message formatting can be tuned independently.
- **Report agent** — formats the Diagnostician's hypothesis + evidence into
  the actual email/Teams message

#### Which specialists run is decided per incident

Not every incident needs every signal. An alert that plainly concerns
infrastructure saturation does not need a trace waterfall, and paying four
models to answer a question one could answer is how a first-pass triage
becomes too expensive to run every hour. So the crew is a set of specialists
that *may* be consulted rather than a list walked in order, and the
Diagnostician picks from it.

That makes the Diagnostician the crew's manager as well as its reasoner, and
it reaches each specialist as a tool it may call. Calling one, reading what
came back, and choosing the next from it is the whole point; handing control
off to a specialist instead would cost the Diagnostician the thread it is
reasoning on. The bound on a manager that keeps asking is therefore
`max_tool_calls_per_agent` applied to it, not `max_agent_hops` — see [Circuit
breakers](#circuit-breakers).

A specialist that was never called is not a specialist that found nothing.
This is the same distinction [Evidence and the platform
boundary](#evidence-and-the-platform-boundary) draws about a failed search,
one level up: an investigation records which signals it consulted, so that a
report saying the logs were clean cannot be read as one where nobody looked at
the logs. Findings carry that alongside the retrieval failures they already
carry.

It is also what makes the routing gradeable. "Did it consult the right
specialists for this incident" is a question with a right answer on a recorded
incident, and it is the first thing the [evaluation
harness](#evaluation-harness) asks — which is why that harness is worth
building only once there is a manager making the choice.

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
not a port — recorded incidents with expected findings, replayed against a
whole investigation. It is owed to the Datadog specialists just as much,
which is why it is a named [next step](#evaluation-harness) rather than a
nicety — outside the MVP, but the first thing after it.

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

Three of these defaults were set against a crew that had one specialist, one
tool, and no manager. What they now bound has moved:

- `max_tool_calls_per_agent` stops being a safety net and becomes a live
  constraint. A specialist with one tool could hardly loop; one with six
  and runtime discovery will, and on Grafana it must spend calls on
  datasource discovery before it can ask anything at all. The bound now
  belongs in `before_tool_callback`, which is a better seat than the old
  design had for it — the callback can refuse a call rather than the
  coordinator counting after the fact.

  It is also what bounds the Diagnostician, since a specialist reaches it as
  a tool: the same key answers "how many searches may one specialist run" and
  "how many specialists may one incident cost", which are different questions
  and may want different values. Whether one key can serve both is a decision
  the harness's numbers should settle rather than one to guess at now.
- `max_agent_hops` was written for a crew that handed off. Specialists called
  as tools do not hand off, so the depth it bounds is the manager's own, and a
  default of 2 admits a specialist and nothing beneath it — the right shape
  while no specialist calls another. It becomes load-bearing again the day
  multi-hop dependency traversal lands, which is a roadmap item.
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
- `DD_WEB_SUBDOMAIN` — where this account's web app is served, defaulting to
  `app`. Only ever the host a link sends a human to: an organisation issued a
  sub-domain of its own serves its pages there and nowhere else, while the API
  and the MCP server keep hosts of their own.
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

v1 runs manually, from a developer's machine. Next step: containerize, so
the same image runs for different teams' configs and a run stops depending on
the machine it was developed on. `docker run` is where the deployment story
stops for now — deliberately, because an image is what any hosted target would
need and choosing one commits to a landscape before there is a reason to. GCP
(a Cloud Run job or GKE) remains the likely destination when that reason
arrives; it is a later decision, not the next step.

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

Individual capabilities left out of v1. The two larger items that follow the
MVP as a whole — measuring investigation quality, and remembering what past
investigations concluded — are under [Next steps](#next-steps-roadmap-after-the-mvp)
after the slice order.

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

   Then a second restructure, of the tree rather than of the investigation:
   the four bounded contexts described under [Architecture](#architecture).
   It belongs to this slice because this slice is what made it necessary.
   Retiring the port grew the ADK adapter to a third of all adapter code, and
   a flat `adapters/` that groups by "this is an integration" was then filing
   an agent subsystem beside a sixty-line dotenv wrapper. The evaluation
   harness is not an adapter and had nowhere to go either; slices 8 and 9 take
   investigation from one specialist to six. Doing it here rather than later meant moving a
   third of the code that a later cut would have had to move.

   Two anticorruption layers keep the contexts acyclic: `InvestigationTarget`
   replaces the incident at the investigation boundary, and `TriageReport`
   trades the whole incident it used to carry for the identifier and service
   that were all production had ever read off it. Both were cheap only because
   the call sites were still few, and neither gets cheaper from here.
   The rules are enforced rather than reviewed — one layers contract per
   context, plus contracts for cross-context privacy, supporting-context
   independence, and a shared kernel that depends on nothing. Each was shown
   red against a deliberate violation before being trusted green, and the
   architecture test names them so that a contract going missing fails a
   build rather than passing one.
8. **Remaining specialist agents** (APM incl. single-hop dependency
   evidence, Trace, Infrastructure) — one declaration each, added
   independently. First of the three because a manager choosing between
   specialists needs specialists to choose between, and because a grader
   worth trusting is one held against a whole investigation rather than
   against the single specialist that happens to exist.
9. **Diagnostician + Report agent** — the Diagnostician decides which
   specialists this incident needs, calling each as a tool, then reasons
   across what they report into a hypothesis with an explicit confidence
   level; the Report agent formats it. Findings gain the record of which
   signals were consulted, so a signal nobody looked at is never read as a
   signal that was clean. Testable against canned findings, with the routing
   testable by asserting which specialists a stubbed manager was offered and
   which it called.
10. **A specialist belongs to its signal, not to one platform** — *done.*
    `adapters/`
    splits by framework and platform, which files each specialist under the one
    vendor it happens to query today. That is about to stop being true: the
    GitHub deploy-history correlation on the roadmap lands on the APM
    specialist, and a specialist reaching two providers has no honest home in a
    tree that assumes one. The move is `adapters/crew/`, holding `specialists/`
    and `reasoners/` as the siblings they are — leaving `adk/` the framework
    machinery that turns a declaration into a running agent, and `datadog/` the
    plumbing that says where its server is and how its items are addressed.
    That also settles an asymmetry slice 9 introduced, where the specialists are
    filed by platform and the two reasoners, belonging to no platform, ended up
    under the framework for want of anywhere better.

    The directory is the symptom rather than the constraint. What actually
    confines a specialist to one platform is that `Deployment` carries a single
    endpoint and one set of headers, and a `Toolset` names a group on *that*
    server — so a declaration cannot reach a second provider however it is
    filed. The slice is therefore the move plus a `Toolset` that names the
    provider serving it and a `Deployment` that maps providers to where they
    are and what authenticates against each.

    A specialist stays platform-*specific*: its tool names and its query dialect
    do not translate, and [What portability now
    means](#what-portability-now-means) is unchanged by this. What stops being
    true is that it belongs to exactly *one* platform.

    Ordered immediately after the crew it reorganises, and before everything
    that would otherwise move twice. The circuit breakers wire configured
    timeouts into the same connection parameters this reshapes; deployment
    packaging and the diagram both describe a tree this changes. The precedent
    is slice 7's own restructure — moving code before more of it accumulates is
    what stopped a later cut having to move a third of the adapter layer. Its
    safety net is the suite it already has, which is what a behaviour-preserving
    move is entitled to: the evaluation harness would score it identically, and
    this does not wait on a roadmap entry to prove a move changed nothing.

    One question it had to answer rather than inherit: once a Datadog logs
    specialist and a Grafana one can sit side by side, both are offered to the
    Diagnostician and the same signal is consulted twice. **Answered by what the
    deployment configured, not by a new setting.** A declaration is offered when
    every provider its toolsets name is one the deployment holds, so a
    deployment with only Datadog credentials never sees the Grafana specialist
    and nothing is consulted twice. Every, not any: a specialist reaching two
    providers where only one is configured is left unoffered rather than run
    against half the evidence it was declared to gather. A deployment holding no
    provider at all is refused while the run is still being assembled.

    An explicit per-deployment allowlist was considered and rejected as a key
    that answers a question credentials already answer. It stays available for
    the deployment that configures two providers and still wants one specialist
    per signal — at which point it joins the open question about naming agents
    under `investigation.specialists`, rather than pre-empting it.

    Testable by the suite it already has, which is the point: the move changes
    no behaviour, so every existing test passes unmoved, and the provider change
    is exercised by one declaration reaching two fake servers. It also rewords
    what `AGENTS.md`, [`docs/adapters.md`](adapters.md) and the `investigation`
    spec say about a specialist living under the platform it queries.
11. **Escalation path** — severity/threshold rule + critical-services
    overrides, bypassing batching. Testable as rule-engine unit tests.
12. **Circuit breakers** — per-agent, per-hop, and per-investigation bounds;
    trip → partial report + auto-escalate. The per-agent bound sits in
    `before_tool_callback`, and the two MCP-level bounds are re-expressed
    through ADK's connection parameters. Testable by forcing a trip
    condition.

    It inherits one thing worth fixing while it is in there. `MAX_CONSULTATIONS`
    sits in `adapters/adk/consultation.py`, stated where it is enforced — the
    same convention `CONNECT_TIMEOUT_SECONDS` follows, and unobjectionable while
    only the enforcing adapter reads it. But the Diagnostician's instruction
    interpolates it too, so after slice 10 that constant is the *only* import
    `adapters/crew/` makes from `adapters/adk/`: a declaration reaching into the
    machinery for a number, in a tree whose point is that declarations do not
    know the framework. Nothing in the constant's own justification is about
    ADK — it counts questions rather than specialists, and eight is chosen
    against `len(CREW)`.

    The bound has two claimants that must never disagree: what the manager is
    *told* it has, and what is *enforced*. Both should read one value neither
    owns, which is `investigation/domain/` now and `configuration/settings.py`
    once this slice makes it configurable — at which point the constant becomes
    the default beside the setting rather than something that moves twice.
    Deliberately left alone in slice 10, because moving it is this slice's work
    and doing it there would have been a behaviour-preserving move carrying a
    design change.

    Worth enforcing rather than re-noticing: `crew` may not import `adk`. The
    machinery depends on the declarations and never the reverse, which is a
    forbidden contract in `.importlinter` — shown red against a deliberate
    `crew → adk` import before it is trusted green, like every other contract
    here.
13. **CI gate failure-mode confirmation** — *done.* The leftover of slice 0:
    a deliberate lint error, a type error, and a boundary violation, each pushed
    alone to a scratch branch, each producing a red run naming the ruff rule and
    location, the offending expression, and the forbidden import. A fourth push
    removed the defect and nothing else, and went green — which is what makes
    the three red runs evidence about the defects rather than about the branch.
    The branch is deleted; the runs are recorded under [Confirmed failure
    modes](spec-process-cicd-ci.md#confirmed-failure-modes), against criteria
    VLD-002…VLD-005. Deferred out of slice 0 because it is the one check that
    cannot be proven locally — it needs real runs on the remote.

    It found a defect as well as confirming a design. A git worktree this repo
    hosts under `.claude/worktrees/` is staged by `git add -A` as a gitlink with
    no `.gitmodules` entry, and `actions/checkout` fails on it before any check
    runs — a red build naming nothing about the change that caused it, which is
    the one failure mode this gate is not allowed to have. The directory is now
    ignored.
14. **Deployment packaging** — containerize. An image that performs one
    complete run unargued, carrying the dependency set the gate verified,
    holding no deployment's secrets, and keeping its ledger on a mounted volume
    so a packaged run is continuous with the one before it. That last part is
    the whole reason this is a slice rather than a Dockerfile: a container's
    filesystem does not survive it, so the ledger's default location silently
    disables dedup, continuation and the re-notify cooldown while the run still
    exits `0`.

    No manifests. Cloud Run and GKE were named here and are deliberately
    dropped: the image is what a hosted target would need, and picking one is a
    later decision this slice is the prerequisite for — see
    [Deployment](#deployment). Nothing publishes the image either; the gate
    builds it, nothing pushes it.

    Testable via container build + smoke test — the image refuses on a missing
    setting and names it, a fully configured run gets through building every
    adapter and creating its ledger on the mount before failing on a platform it
    cannot reach, and a second container over the same mount keeps what the
    first one left. The green-path run is not exercised through the container:
    the Datadog URL this project composes is https-only, so a fake platform
    needs a TLS sidecar and a trusted CA inside the image, to re-prove run logic
    the in-process end-to-end test already covers.
15. **README architecture diagram rework** — the diagram the bounded-context
    restructure left behind states the shape correctly and reads poorly: four
    nested subgraphs, an enclosing box for configuration, and a rung per layer
    inside each context, all competing for the same glance. Deliberately last,
    because every slice before it changes what the picture has to say. Slice 9
    moves report formatting into an agent, which dissolves triage's deep read
    of investigation's vocabulary and so redraws one of the two cross-context
    edges. Slice 11 adds a path that bypasses batching entirely, which the
    current picture has nowhere to put. Slice 14 introduces a deployment story
    a reader will want to see — an image, a mounted ledger, and what a run needs
    given to it from outside — and there is no version of that in it today.
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

## Next steps (roadmap, after the MVP)

The slices above are what it takes to have the thing working: alerts in,
investigated, a report out. What follows is what it takes to have it working
*well*. Neither entry can be built usefully before there is a running system to
measure and a history to remember, which is why both sit after the slice order
rather than inside it. They are ordered with respect to each other — memory
depends on the harness, for the reason given below.

### Evaluation harness

Recorded incidents replayed against a whole investigation, so quality is
measurable rather than felt. A case is captured once from the live platform —
every tool declaration, call, and result — and replayed from disk thereafter,
so the platform's answer is fixed and a change in the score is a change in the
instruction, the routing, or the model rather than in Datadog.

The judgements most worth grading are which specialists an incident needed and
what the Diagnostician concluded from them, so the crew has to exist first.
Grading a lone specialist would mean inventing a standard for a whole
investigation and then revising it the moment the manager arrived. It settles
the questions slice 6 left open — which model to default to, and how many
examples a finding should carry — and gives slice 12 evidence where it
currently has guesses.

Out of the MVP rather than in it, because an MVP is judged by whether a human
opening the report finds it useful, and that judgement is available by reading
one. Measuring it is what you need in order to *improve* it deliberately, and
that is a problem worth having only once something is running to improve.
Testable as a scoring run over recorded cases.

### Memory — what past investigations learned

The ledger remembers what was *reported*. Nothing remembers what was
*learned*. So a problem that recurs every week is investigated from scratch
every week, at full model cost, and may reach a different conclusion than last
time for no reason other than sampling. The knowledgeable human this project
stands in for does not work that way: the third time they see a symptom they
recognise it, and most of their speed comes from that rather than from
searching faster.

Memory is that record — what an investigation concluded, against what
signature, and what happened afterwards — kept so that a later investigation
can find it.

It belongs to `investigation`, not to triage. What is remembered is findings
and hypotheses, which are investigation's own vocabulary; holding them in
triage would mean triage learning that vocabulary, and the contract exists
precisely so it does not have to. So: a `Memory` port declared in
investigation, written at the end of an investigation and read by the
Diagnostician as one more tool it may call — the same shape a specialist
already has, which means the manager decides per incident whether prior
knowledge is worth consulting rather than paying for a lookup every time.

The payoff is routing before it is confidence. A Diagnostician that knows this
signature has recurred three times, and what each turned out to be, can skip
the specialists that found nothing on any of them — and the cost of an
investigation is dominated by which specialists run. Better-grounded
hypotheses are the second benefit, not the first.

Four things to design against from the start:

- **A memory is a hypothesis, not a fact.** This system deliberately produces
  a hypothesis with a confidence level rather than a verdict. Storing one and
  then leaning on it is how an unexamined guess becomes permanent truth. A
  memory has to carry the confidence it was formed with and whether a human
  ever confirmed it — which is the same missing input as
  [Acknowledgement](#acknowledgement--the-missing-input), and the reason these
  two are related rather than independent.
- **Anchoring is the failure mode, not a wrong memory.** A Diagnostician told
  "last time it was the database" may stop looking. Memory should bias which
  signals get consulted and never substitute for consulting them: a recalled
  cause enters as a lead that a specialist must corroborate against today's
  evidence, carrying its own citation. A finding that cites only a memory is
  not a finding, by the same rule that already discards one citing nothing.
- **Recall is a matching problem, and the grouping key does not solve it.**
  Service plus time window says two alerts are the same incident. It says
  nothing about two incidents a month apart being the same *problem*. That
  needs a notion of similarity over the alert signature and the findings.
  Start with the cheapest thing that could work — service, monitor identity,
  and signal — and let the harness say whether it has to be cleverer.
- **A fixed problem makes its memory wrong.** A memory's value decays, and a
  deploy is the event most likely to invalidate one outright. The
  change-story tools the APM specialist already reaches are what would notice,
  so invalidation is a rule over evidence the system already gathers rather
  than a new integration.

Ordered after the harness deliberately. "Does memory make investigations
faster and more accurate" is exactly the question a scoring run over recorded
cases answers, and without it memory is a plausible-sounding change nobody can
tell is working — including in the direction where anchoring quietly makes it
worse. Building the harness first is what makes memory an experiment rather
than a belief.
