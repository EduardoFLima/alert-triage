# The log a run writes

A run is a batch job. Nobody watches it happen, and by the time anyone reads
about it the process is gone — so its log is the only account of what it did.
It is written for a human reading a terminal at three in the morning rather
than for a parser, and it goes to stderr.

Two things follow from that. The account is the *run's*, not the frameworks'
underneath it, and it is shaped so a reader can find the moment they came
looking for without reading the rest.

## Two weights, and no more

**A phase of a run is boxed.** `FETCHING ALERTS`, `INCIDENT`, `INVESTIGATING`,
`INVESTIGATION CONCLUDED`, `REPORTING`, and the `TRIAGE RUN` / `RUN COMPLETE`
either side of them. A box says a reader has arrived somewhere new, and every
box names what it concerns, so a block that could belong to any of three
services never happens.

**A moment within a phase is captioned** under a `──` rule: a consultation, a
tool call, what came back, what an agent said. Details are aligned in a column
beneath either, and a value too long for its column is given its own lines
rather than run off the edge.

A third weight would only blur the difference between the two, so there isn't
one.

**Every record is followed by a blank line**, blocks and one-liners alike. That
is the log handler's doing rather than any one message's, because the record
that most needs separating is the one nothing composed: an exception's stack
trace, which would otherwise run straight into whatever is logged after it.

## When something goes wrong

Failures are written in the same two weights, and which one a failure takes is
decided by its *consequence*, not by its level:

- **A failure that ends the run is boxed** — the deployment refusing to start,
  or a fetch that came back with nothing to work on. Nothing follows it, so
  nothing else will tell a reader why the log stops.
- **A failure contained to one group or one consultation is captioned** under
  the phase it happened in — a ledger that would not read, an investigation
  that errored, a report no channel took, a citation that resolved to nothing.
  The run carries on around it, and so does the log.

How bad it is stays where it always was: the level every record already
carries. `WARNING` is the run degraded — a report composed because the writer
failed, a finding dropped because its evidence was never retrieved, one channel
of several refusing delivery. `ERROR` is something it set out to do and could
not.

```
2026-09-01 09:41:02 ERROR    alert_triage.app.pipeline
╭──────────────────────────────────────────────────────────────╮
│ FETCH FAILED                                                 │
╰──────────────────────────────────────────────────────────────╯
  detail   Could not fetch alerts for owner 'sre' from Datadog:
           403 Forbidden

2026-09-01 09:41:26 WARNING  …adapters.adk.investigator
  ── the report could not be worded ────────────────────────────
  service   checkout
  detail    the model refused
  instead   composed from what was found
```

A run closes by naming every stage it could not complete, each as its own
block under `RUN COMPLETE`, so the account ends with what it owes rather than
leaving a reader to scroll for it.

## A run, read back

```
2026-09-01 09:41:03 INFO     alert_triage.app.pipeline
╭──────────────────────────────────────────────────────────────╮
│ INCIDENT · checkout                                          │
╰──────────────────────────────────────────────────────────────╯
  alerts   4
  window   2026-09-01T09:12:00+00:00 → 2026-09-01T09:38:00+00:00

2026-09-01 09:41:07 INFO     …adapters.adk.reasoning
  ── diagnostician reasoning ───────────────────────────────────
  Error rate and latency both moved at 09:14, which is when the
  deploy landed. Latency alone would point at a dependency; both
  together points at the service itself. I will read the logs
  first and let what they say choose the next specialist.

2026-09-01 09:41:07 INFO     …adapters.adk.consultation
  ── consulting logs_specialist ────────────────────────────────
  request   Errors for checkout between 09:12 and 09:38, with
            anything unusual around the 09:14 step change.

2026-09-01 09:41:09 INFO     …adapters.adk.evidence
  ── logs_specialist → search_datadog_logs ─────────────────────
  query   service:checkout status:error
  from    2026-09-01T09:12:00Z
  to      2026-09-01T09:38:00Z
  limit   50

2026-09-01 09:41:11 INFO     …adapters.adk.evidence
  ── logs_specialist ← search_datadog_logs ─────────────────────
  call       call-1
  items      12
  answered
    {'logs': [{'message': 'OOMKilled: container checkout
    exceeded its memory limit', 'host': 'ip-10-0-4-91',
    'timestamp': '2026-09-01T09:14:12Z'}… [1369 more characters]

2026-09-01 09:41:14 INFO     …adapters.adk.consultation
  ── logs_specialist reported ──────────────────────────────────
  The checkout pods are being OOM-killed repeatedly from 09:14
  onward: 37 error lines in the window, 31 of them the same
  OOMKilled message against three different pod identities, so
  this is the whole replica set rather than one unlucky host.
  The first kill lands 90 seconds after the 09:13:30 deploy
  event that also appears in the log stream.

  signal     logs
  findings   1, over 31 occurrence(s)
  evidence   call-1/item-1, call-1/item-3

2026-09-01 09:41:23 INFO     …adapters.adk.investigator
╭──────────────────────────────────────────────────────────────╮
│ INVESTIGATION CONCLUDED · checkout                           │
╰──────────────────────────────────────────────────────────────╯
  consulted    logs_specialist, infrastructure_specialist
  signals      logs, infrastructure
  findings     2
  hypothesis   The 09:13:30 deploy introduced a per-request
               memory leak; pods reach the unchanged 512 MiB
               limit and are OOM-killed from 09:14 onward.
  confidence   high

2026-09-01 09:41:24 INFO     …adapters.adk.reasoning
  ── report_writer answered ────────────────────────────────────
  headline    checkout is OOM-killing after the 09:13 deploy
  narrative   Checkout has been restarting since 09:14. Every
              pod in the replica set reaches its 512 MiB limit
              within four minutes of starting and is killed.
```

## What reaches `INFO`

Everything above, which is to say:

- **Each phase of a run**, and what it concerns.
- **Every consultation**, and the question the diagnostician wrote for it. A
  consultation that was refused because the incident spent its questions, or
  that failed outright, says so.
- **Every tool call a specialist makes**, when `LOG_TOOL_CALLBACK` asks for
  them — the arguments on the way out, and the retrieval identifier, the item
  count and a bounded look at the payload on the way back. This is the one part
  of a run's own account held back by default: it is the bulk of the output, and
  what a specialist was asked and what it concluded is the account while the
  queries beneath are the working. A retrieval that *failed* is not working —
  it is why a report is incomplete — so it is written down whatever the flag
  says, as a failure and never as an answer.
- **What each specialist observed, in full.** Never shortened: it is the
  investigation's own characterisation of what it saw, it is what a reader came
  for, and half of it is worse than none. A specialist whose report bore
  nothing out says exactly that — silence there would read as a specialist
  nobody asked.
- **What both reasoners said.** The diagnostician's thread between
  consultations is the only account of why it asked what it asked; the report
  writer's turn is the report taking shape. An agent's final turn is its output
  schema, and is read back as the fields it declared rather than reaching the
  log as JSON.

Only the values a run passes *through* are ever shortened — a platform's
answer, a tool's arguments — and a shortened value says how much it dropped.

## What does not, and how to get it

The frameworks underneath keep an account several times longer than the run's
— every model turn, every session the runner opens, every HTTP request a tool
makes — and they write it at `INFO` too. Left alone, the run's own account is a
few lines in thousands. So `google`, `google_adk`, `google_genai`, `httpx`,
`httpcore`, `urllib3`, `mcp`, `asyncio` and `datadog_api_client` are held at
`ERROR`.

`ERROR` rather than `WARNING` because a framework's warnings are about itself
rather than about this run — an experimental feature flag being enabled, a
channel that is not mTLS. Both arrive on every run whatever is happening, which
makes them noise rather than news. What is still let through is a framework
saying it could not do the thing it was asked to do.

Some of that talk never reaches a logger at all: ADK announces its experimental
features through Python's `warnings`, which prints to stderr past every level.
Those are routed into the log with `logging.captureWarnings` and held with the
frameworks that raise them, so one policy covers both.

`LOG_LEVEL` releases all of it:

| `LOG_LEVEL` | The run | Its tool calls | The frameworks, and Python's warnings |
| --- | --- | --- | --- |
| `DEBUG` | everything, plus its own debug lines | always | everything |
| `INFO` (default) | its whole account | only with `LOG_TOOL_CALLBACK` | only what they could not do |
| `WARNING` | only what went wrong | no | only what they could not do |

`LOG_TOOL_CALLBACK=true` adds the tool calls at `INFO` without turning the
frameworks on with them, which is the difference between wanting to see what a
specialist asked the platform and wanting to debug ADK.

It is read from the environment, `.env` included, at the same moment the run
resolves everything else it is configured from — so it is settled before the
run says anything. A name outside that set is refused out loud and the run
starts at `INFO` anyway: a typo in an environment costs a deployment its
verbosity, never its triage.

`pytest` is not covered by any of this. It captures Python warnings itself and
reports them in its own summary, which is where a developer should see a
library's deprecations.

## Where it lives

- [`shared/journal.py`](../src/alert_triage/shared/journal.py) — the vocabulary
  above: `banner`, `event`, and `shortened`. Every context writes its account
  through it, so a reader cannot tell which of them wrote which block. It is in
  the shared kernel because it is vocabulary rather than behaviour, and it
  depends on nothing but the standard library.
- [`app/verbosity.py`](../src/alert_triage/app/verbosity.py) — the level, the
  held frameworks, the warnings routing, and whether the tool calls are written
  down, settled once at the entrypoint so that importing the pipeline configures
  nothing on its caller's behalf. The tool calls are held by holding one logger
  name, declared beside the callbacks that write to it as `TOOL_CALL_LOGGER`:
  the callbacks still run — the one that keeps the evidence has to — and only
  their account of themselves is held.

Nothing in either decides *what* is worth writing down. That belongs to the
code that knows what just happened.
