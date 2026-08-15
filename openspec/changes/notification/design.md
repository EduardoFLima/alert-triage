## Context

See proposal.md — Why. The state this builds on: `domain/triage.py` produces a
`TriageDecision` whose `should_report` nobody can act on, three layers exist
(`domain`, `ports`, `adapters`) with the import-linter contracts in
`pyproject.toml` enforcing the direction between them, and slice 2 established
that behavior lives in `config.yaml` while connections live in the environment.
`adapters/email/` and `adapters/teams/` exist as empty packages from slice 0.

Two constraints shape everything below. There is still no composition root, so
this slice must produce something slice 5 can inject without further shaping.
And the report's *content* belongs to slice 8, so the report type this slice
introduces has to be the one slice 8 fills in rather than one it replaces.

## Goals / Non-Goals

**Goals:**

- A `Notifier` port whose contract is small enough that a third channel is a
  new file and nothing else.
- Fan-out that behaves under partial failure the way the ledger needs it to,
  so slice 5's "record as reported" question has a one-bit answer.
- Both adapters testable with no network and no mail server, in `tests/unit/`.

**Non-Goals:**

- Report content. `TriageReport` carries a subject and a plain-text body; what
  goes in them is slice 8's Report agent.
- Choosing a channel per incident, per severity, or per service. Escalation
  (slice 9) is the first thing that needs a report to take a different route,
  and it will need the escalation rule before it needs the routing.
- Rich Teams interaction — buttons, reactions, threading. Acknowledgement is a
  roadmap item in `docs/vision.md`, and it is inbound; this port is one-way.
- Batching or digesting several incidents into one message. One report, one
  incident.
- Templating. A subject line and a body do not need a template engine, and one
  would be a dependency in the layer that has the fewest.

## Decisions

### `TriageReport` is a domain value, not a string

The port takes a `TriageReport` — incident id, service, subject, body — rather
than a rendered message. Alternatives were passing an `Incident` and letting
each adapter render it, or passing a formatted string.

Passing the `Incident` puts the same formatting decision in every adapter and
guarantees two channels drift apart. Passing a string throws away the incident
identity, which the Teams card wants for its own subtitle and which
acknowledgement will need something stable to attach to. A thin value in the
middle is what lets slice 8 change what a report *says* without any adapter
noticing, which is the whole reason the vision keeps Diagnostician and Report
as separate agents.

`TriageReport` lives in `domain/report.py` and depends only on `Incident`.

### Fan-out is itself a `Notifier`

`FanOutNotifier` implements the port it composes. Slice 5 injects one
`Notifier` and never learns whether one channel or three sit behind it, and a
single-channel deployment is not a special case.

The alternative — the composition root looping over a list of notifiers — puts
the partial-failure rule in the composition root, where it cannot be unit
tested without building a pipeline around it.

### Success means at least one channel accepted; failure means none did

Attempt every channel; collect the failures; raise `NotifierError` only when
the successes are empty. The rationale is downstream: slice 5 records the
incident as reported only when delivery succeeded, and "the team was told"
is true as soon as one channel got through. Raising on any failure would let a
broken SMTP relay stop the cooldown from ever starting, and the incident would
be re-reported to Teams every single run — the alert fatigue this project
exists to reduce.

The failure raised when every channel failed carries each channel's own
failure, not just the last: an operator debugging "no reports are arriving"
needs both reasons at once.

A partial failure must not vanish. It is logged through the standard library's
`logging` at warning level, from the fan-out notifier. A `Logger` port is
deliberately not introduced here — the first thing that would justify one is
structured output in a deployed environment (slice 12), and inventing it now
would mean designing an interface against a single caller.

### Retry is the next run's job

No retry loop, no backoff. A run that delivered nothing does not record the
incident as reported, so the next scheduled run produces the report again — the
ledger already is the retry mechanism, and it is durable across processes in a
way an in-run retry is not. This also keeps a run's duration bounded without a
new circuit breaker.

Each adapter still sets a socket-level timeout, so a hung destination cannot
hold the run open indefinitely. A fixed documented default (30 seconds), not a
setting: there is no evidence yet for what an operator would tune it against,
and `docs/vision.md` is explicit that a setting is added when it answers a
question someone actually has.

### Email over `smtplib`, with the connection resolved from the environment

`smtplib` plus `email.message.EmailMessage` covers submission, TLS, and
authentication with no dependency at all, and `smtplib` is already in the
`forbidden_modules` contract — the architecture test catches a regression that
pulls it into the core before a human would.

Settings, all environment-only, following the `DD_*` and
`ALERT_TRIAGE_LEDGER_PATH` precedent and resolved by a `resolve_*` function
beside the adapter exactly as `resolve_connection` and `resolve_ledger_path`
are:

| Variable | Required | Default |
|---|---|---|
| `ALERT_TRIAGE_SMTP_HOST` | yes, to activate the channel | — |
| `ALERT_TRIAGE_SMTP_PORT` | no | 587 |
| `ALERT_TRIAGE_SMTP_USERNAME` | no (unauthenticated relays exist) | — |
| `ALERT_TRIAGE_SMTP_PASSWORD` | with a username | — |
| `ALERT_TRIAGE_EMAIL_FROM` | yes, when the host is set | — |
| `ALERT_TRIAGE_EMAIL_TO` | yes, when the host is set | — |

The host is what activates the channel; the rest being absent alongside it is a
half-configured channel and a `ConfigError`, per the config delta. STARTTLS is
attempted by default on the submission port; a password without a username (or
the reverse) is likewise a configuration error rather than a silent fallback to
an unauthenticated send.

Note the hazard: the package is `alert_triage.adapters.email`, and the standard
library module it uses is `email`. Absolute imports mean
`from email.message import EmailMessage` inside that package resolves to the
standard library, and a test asserting exactly that is cheap insurance against
a future relative import breaking it in a way that only shows up at runtime.

### Teams over a Workflows webhook and an Adaptive Card

Microsoft retired the Office 365 connectors that the classic
`outlook.office.com/webhook/…` URLs belonged to. The supported replacement is a
Power Automate flow triggered by "when a Teams webhook request is received",
which accepts an Adaptive Card wrapped in a message envelope and answers 202.

Chosen over Microsoft Graph, which would need an app registration, a tenant, a
client secret, `msal`, and channel ids — a new dependency and a much larger
operator setup, for no gain while the port stays one-way. If acknowledgement
later arrives via Teams, it will need Graph anyway; that is a slice with its
own budget, and this adapter's rendering survives it.

Transport is `urllib.request` rather than `requests` or `httpx`: one POST of a
JSON body, and adding an HTTP dependency for it would be paying a supply-chain
cost for convenience. `urllib.request` joins `forbidden_modules` for symmetry
with `smtplib`.

`ALERT_TRIAGE_TEAMS_WEBHOOK_URL` activates the channel and is its only setting.
Any non-2xx response, or a transport error, is a `NotifierError` carrying the
status and the response body — Workflows reports a malformed card as a 4xx with
a body worth reading.

The exact envelope and Adaptive Card schema version are to be confirmed against
current Microsoft documentation during implementation, per `AGENTS.md` — the
shape is `{"type": "message", "attachments": [{"contentType":
"application/vnd.microsoft.card.adaptive", "content": {…card…}}]}`, and the
card body is a title block plus the report body as text.

### Rendering lives with the channel; both adapters take a pure render function

Each adapter separates "turn a `TriageReport` into this channel's payload" from
"send this payload". The rendering half is a pure function tested directly on
its output; the sending half is thin enough to test by injecting the standard
library's client — `smtplib.SMTP` as a factory argument, and the opener for
`urllib.request` — with a fake. That keeps `tests/unit/` free of a network and
a mail server, which is what `AGENTS.md` requires of that directory, and leaves
`tests/integration/` for a real send against a local SMTP debugging server.

### Channel resolution decides what exists, and refuses when nothing does

One function assembles the fan-out notifier from the environment: it activates
each channel whose settings are present, raises `ConfigError` for a channel
configured in part, and raises `ConfigError` when no channel is configured at
all. It lives in the adapters layer, not `app/` — there is no composition root
yet, and putting it beside the adapters lets slice 5 call one function.

Refusing on zero channels is the same rule as the mandatory `scope.owner`: a
run that cannot tell anyone anything has no reason to start, and finding out at
startup beats finding out when the first report is due.

## Risks / Trade-offs

- **A partial failure is only a log line.** A team whose email has been broken
  for a week learns nothing from Teams reports that keep arriving → Accepted
  for this slice, and cheap to improve later: the fan-out already knows every
  failure, so a future slice can annotate the next report with "email delivery
  has been failing" without changing the port.
- **Workflows webhooks are a Microsoft product decision away from moving
  again**, as connectors just were → The blast radius is one adapter behind a
  port that knows nothing about HTTP. The rendering/sending split means a
  transport swap does not touch the card.
- **No delivery receipt.** SMTP submission accepted is not "read", and a 202
  from a Workflows flow is not "posted to the channel" → Inherent to both
  mechanisms. It is also precisely the gap `docs/vision.md` names as the
  acknowledgement roadmap item, so this slice should not pretend to close it.
- **Secrets in environment variables.** An SMTP password sits in the process
  environment → Same posture the Datadog credentials already established, and
  the reason no channel setting is readable from `config.yaml`: there is never
  a key shaped like a credential for someone to fill in and commit.
- **Six environment variables for one channel** is a lot of setup for a manual
  v1 run → Only the host, sender, and recipients are required, and the Teams
  channel needs exactly one variable. A deployment can configure Teams alone
  and never touch SMTP.
