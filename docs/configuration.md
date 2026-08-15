# Configuration

Two kinds of setting, and which kind a value is decides where it goes.

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
```

Set `scope.owner` to the team that owns the alerts you want triaged; the
Datadog adapter spends it as a `team:` term in its event query. Keep
`ingestion.lookback_seconds` comfortably wider than the interval the job runs
on, so a delayed run does not step over alerts — re-delivered alerts are
recognised and absorbed rather than reported twice.

`re_notify.cooldown_seconds` and `ledger.retention_seconds` are tuned
separately and neither is derived from the other: the first is how often a
still-firing incident is re-reported, the second is how far back you can look
at what was reported. Setting retention shorter than the cooldown cannot
resurrect duplicate reports — retention is counted from the moment an incident
*closes*, and closing already requires the cooldown to have elapsed.

## Connection: the environment

Writing any of the settings below into `config.yaml` has no effect — the key is
inert, and resolution proceeds as if it were absent.

### Datadog

Under Datadog's own variable names, so an operator who already exports
`DD_API_KEY` for the CLI exports nothing new:

```bash
export DD_API_KEY=...      # required
export DD_APP_KEY=...      # required; the Events API needs both
export DD_SITE=datadoghq.eu  # optional, defaults to datadoghq.com
```

### The triage ledger

Where the ledger keeps its records is a deployment fact on the same rule — with
a default, since a path is not a credential:

```bash
export ALERT_TRIAGE_LEDGER_PATH=/var/lib/alert-triage/ledger.db
# optional; defaults to alert_triage.db in the working directory
```

The ledger is a SQLite database, created with its schema on first use. A first
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
sqlite3 alert_triage.db \
  "SELECT id, service, last_reported_at, closed_at FROM incidents;"
```

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
