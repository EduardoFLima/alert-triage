# Configuration

Two kinds of setting, and which kind a value is decides where it goes.

Each kind ships an annotated example naming every setting it holds, its
default, and whether it is mandatory: [`config.example.yaml`](../config.example.yaml)
and [`.env.example`](../.env.example). Copy them rather than starting from a
blank file — a test fails if either drifts from the schema it describes.

*Behavior* — what the system watches and how it triages — lives in an optional
`config.yaml`. *Connection* — where a platform is, how to authenticate, and
where reports are sent — is read from the environment only.

That rule applies to any new setting too: if it changes when the same triage
behavior is pointed at a different account, region, or team, it is a connection
setting and belongs in the environment. Otherwise it is behavior and belongs in
the file. It keeps a config file portable across deployments, and keeps
anything credential-shaped out of a file that gets committed.

## Behavior: `config.yaml`

Every key here can also be set as an environment variable by mapping its
`section.key` path to `SECTION_KEY`. When both are set, the environment wins.

```yaml
scope:
  owner: sre              # mandatory: whose alerts are triaged. No default.
grouping:
  window_seconds: 1800    # alerts of one service this close are one incident
ingestion:
  lookback_seconds: 3600  # how far back a run looks for alerts
re_notify:
  cooldown_seconds: 172800  # how long a report suppresses the next one (2 days)
ledger:
  retention_seconds: 2592000  # how long closed incidents are kept (30 days)
investigation:
  model: gemini-2.5-flash   # what every specialist reasons on by default
  max_attempts: 3           # investigations one incident may be given in total
```

Set `scope.owner` to the team that owns the alerts you want triaged; the
Datadog adapter spends it as a `team:` term in its event query. Keep
`ingestion.lookback_seconds` comfortably wider than the interval the job runs
on, so a delayed run does not step over alerts — re-delivered alerts are
recognised and absorbed rather than reported twice.

An investigation runs a crew of specialists, one per observability signal, and
`investigation.model` is what each of them reasons on. One that wants a
stronger model than its siblings is named under `investigation.specialists`;
[`config.example.yaml`](../config.example.yaml) lists the names that may be
used, and a name nobody declared is refused while the run is still being
assembled rather than at the first investigation.

`re_notify.cooldown_seconds` and `ledger.retention_seconds` are tuned
separately and neither is derived from the other: the first is how often a
still-firing incident is re-reported, the second is how far back you can look
at what was reported. Setting retention shorter than the cooldown cannot
resurrect duplicate reports — retention is counted from the moment an incident
*closes*, and closing already requires the cooldown to have elapsed.

## Connection: the environment

Writing any of the settings below into `config.yaml` has no effect — the key is
inert, and resolution proceeds as if it were absent.

### Where the environment comes from: `.env`

The variables below can be exported by hand, or written into a `.env` file in
the directory a run is started from. The file is read once at startup, before
anything is resolved, and every name in it is one that could equally have been
exported — it introduces no setting of its own and no second syntax to learn.

```dotenv
DD_API_KEY=...
DD_APP_KEY=...
export ALERT_TRIAGE_EMAIL_TO="sre@example.com,oncall@example.com"
```

Comments, quoted values, and an `export` prefix are all understood; a bare
`NAME` with no value declares nothing and is dropped rather than carried as an
empty string.

**The process wins.** A name the environment already carries is never
overridden by the file, so a container, a systemd unit, or a CI secret keeps
its value even when a stray `.env` sits beside the checkout. The file is a
convenience for a laptop, not a deployment mechanism — which is also why it is
gitignored and only [`.env.example`](../.env.example) is committed.

Because the path is relative, a run started from another directory finds no
file and reads the process environment alone. That is not an error: a
deployment that exports everything needs no file at all.

### Datadog

Under Datadog's own variable names, so an operator who already exports
`DD_API_KEY` for the CLI exports nothing new:

```bash
export DD_API_KEY=...      # required
export DD_APP_KEY=...      # required; the Events API needs both
export DD_SITE=datadoghq.eu  # optional, defaults to datadoghq.com
export DD_WEB_SUBDOMAIN=foobar  # optional, defaults to app
```

`DD_WEB_SUBDOMAIN` is only ever the host a link sends a human to. Datadog
serves most accounts from `app.<site>`, but an organisation may be issued a
sub-domain of its own — `foobar.datadoghq.eu` — and the pages it serves are
reachable only there. The API and the MCP server have hosts of their own, so
setting this moves the links in a report and nothing else.

### The model an investigation reasons on

Under the Google GenAI SDK's own variable names. Which model runs is behavior
and belongs in `config.yaml`; what it costs to reach is a deployment fact:

```bash
export GOOGLE_API_KEY=...    # required, or GEMINI_API_KEY
```

A deployment on the enterprise platform authenticates with the credentials it
already holds, and needs no key at all:

```bash
export GOOGLE_GENAI_USE_ENTERPRISE=true
export GOOGLE_CLOUD_PROJECT=triage-prod     # optional; discovered if unset
export GOOGLE_CLOUD_LOCATION=europe-west4   # optional; defaults to global
```

A run resolves these itself and hands them to the model, rather than leaving
the SDK to read the process environment behind it. That is what lets them live
in `.env` like everything else — and what makes the startup refusal mean
something, since the value a run refuses on is the value its model is built
from.

**One exception.** `GOOGLE_APPLICATION_CREDENTIALS` is read by the Google auth
library straight from the process environment, before the `.env` file is
consulted. A service-account path written in `.env` is not found. Export it, or
use `gcloud auth application-default login`.

### The triage ledger

Where the ledger keeps its records is a deployment fact on the same rule — with
a default, since a path is not a credential:

```bash
export ALERT_TRIAGE_LEDGER_PATH=/var/lib/alert-triage/ledger.db
# optional; defaults to data/alert_triage.db under the working directory
```

The ledger is a SQLite database, created with its schema on first use, along
with the directory it sits in. At the default path that directory is `data/`,
which the repository ignores: a checkout you run from collects its state there
rather than beside the source. A first
run against an empty one has nothing on record, so every alert group it finds
opens a new incident and is reported — there is no migration step and an empty
ledger is not an error. Because the default path is relative, a run started
from another directory starts from an empty ledger and re-reports everything;
set the variable explicitly for anything but a quick local run.

Incidents that have gone quiet past both the grouping window and the cooldown
are closed and kept for the retention period. To read that history — what was
reported, when, and for which alerts — open the database file with any SQLite
client:

```bash
sqlite3 data/alert_triage.db \
  "SELECT id, service, last_reported_at, closed_at FROM incidents;"
```

### How much a run says out loud

How verbose the log is, on the same rule as the ledger's path — a deployment
fact with a default, and not a credential:

```bash
export LOG_LEVEL=DEBUG
# optional; defaults to INFO
```

`INFO` is the run's own account: each phase, every consultation, every tool
call, what each specialist observed, and what both reasoners said. The
frameworks underneath are held at `ERROR` so that account stays readable, and
`DEBUG` releases them — ADK's own lines, the model SDK's, and every HTTP
request a tool makes. A name outside the declared set is refused out loud and
the run starts at `INFO` anyway.

A run's tool calls are the one part of its own account held back by default,
because they are the bulk of its output and most readings do not want them:

```bash
export LOG_TOOL_CALLBACK=true
# optional; defaults to no
```

With it, every query a specialist sends and a bounded look at what came back are
written down. Without it, the consultations and what each specialist observed
still are — the account without the working. A value that is neither a yes
(`1`, `true`, `yes`, `on`) nor a no (empty, `0`, `false`, `no`, `off`) is refused
out loud and read as a no, and `LOG_LEVEL=DEBUG` brings the tool calls back
whatever this says.

What each level shows, and what the log looks like, is in
[`logging.md`](logging.md).

### Notification channels

Which channels are active follows from which of them you configured. Configure
at least one, or the run refuses to start, the same way it refuses a missing
`scope.owner` — a run that can investigate but can tell nobody what it found
has no reason to start.

**Email.** The host activates the channel; the sender and recipients are then
required, and a half-configured channel is an error rather than a silent skip.

```bash
export ALERT_TRIAGE_SMTP_HOST=smtp.example.com
export ALERT_TRIAGE_EMAIL_FROM=triage@example.com
export ALERT_TRIAGE_EMAIL_TO=sre@example.com,oncall@example.com  # comma-separated
export ALERT_TRIAGE_SMTP_PORT=587        # optional, defaults to 587
export ALERT_TRIAGE_SMTP_USERNAME=triage # optional, but paired with the password
export ALERT_TRIAGE_SMTP_PASSWORD=...    # optional, but paired with the username
```

STARTTLS is attempted on every submission and used when the relay offers it; a
relay that does not offer it still receives the report, but a *password* is
never sent over a connection that stayed in the clear — configure such a relay
without credentials, or use one that offers STARTTLS.

**Microsoft Teams.** One variable, and it both names the destination and
authorises posting to it.

```bash
export ALERT_TRIAGE_TEAMS_WEBHOOK_URL=https://prod-1.westeurope.logic.azure.com/...
```

The URL is a [Power Automate Workflows][workflows] webhook — create a flow from
the "Post to a channel when a webhook request is received" template and paste
the URL it gives you. This replaces the retired Office 365 connector webhooks,
whose `outlook.office.com/webhook/…` URLs no longer work.

[workflows]: https://support.microsoft.com/en-us/office/creating-a-workflow-from-a-channel-in-teams-242eb8f2-f328-45be-b81f-9817b51a5f0e

### How delivery behaves across channels

A report goes to every configured channel. One channel failing does not stop
another from being tried, and delivery counts as successful as soon as one
channel accepted the report — a report that reached Teams is worth more than
one that reached nobody because the relay was down. The channels that failed
are logged at warning level. Only when *every* channel fails is the report
undelivered, and then the incident is not recorded as reported, so the next run
produces it again: the ledger is the retry mechanism, and there is no retry
loop inside a run.
