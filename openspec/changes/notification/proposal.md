## Why

Slice 3 gave the system memory: it now knows which incidents are open and
which of them are due to be reported. Nothing can act on that verdict — there
is no way for a triage report to leave the process, so `should_report` is a
boolean nobody reads.

This is slice 4 of the capability breakdown in `docs/vision.md`: the `Notifier`
port and its first two adapters, Email and Teams. Delivery is built before
investigation on purpose — a report's *content* is slice 8's problem, and
proving the channels work against stub content keeps the two independently
testable.

## What Changes

- Add a `TriageReport` domain value: what the system has to say about one
  incident — the incident it concerns, a one-line subject, and a plain-text
  body. Deliberately channel-neutral and deliberately thin: slice 8's Report
  agent fills the body with findings, and nothing in this slice should have to
  change when it does.
- Add a `Notifier` port: deliver one report, or fail. Synchronous, matching
  `AlertSource` and `TriageLedger`. A `NotifierError` is defined beside it, on
  the rule the other two ports already follow — a caller must be able to tell
  "delivered" from "not delivered" without importing anything channel-specific.
- Add an **Email adapter** over the standard library's `smtplib` and
  `email.message`. No new runtime dependency, and the boundary contract in
  `pyproject.toml` already names `smtplib` as forbidden to the core, so a
  regression that pulled SMTP into the domain fails the architecture test.
- Add a **Teams adapter** posting an Adaptive Card to a Power Automate
  Workflows webhook, over the standard library's `urllib.request`. Microsoft
  retired the Office 365 connector webhooks the classic
  `outlook.office.com/webhook/…` URL belonged to; the Workflows webhook is
  their supported successor and keeps the same deployment shape — one URL in
  the environment, no app registration, no token flow.
- Add a **fan-out notifier** that delivers to every configured channel and does
  not let one channel's failure stop another's. A report that reached Teams is
  worth more than a report that reached nobody because the SMTP relay was down.
  It fails only when **no** channel accepted the report — which is exactly the
  condition under which slice 5 must not mark the incident reported, so the
  next run tries again. Retry is therefore the ledger's existing behavior, not
  a new mechanism.
- Resolve every channel's settings — SMTP host and port, sender and recipients,
  webhook URL — **from the environment only**, on the boundary slice 2 drew and
  `docs/vision.md` applies to this exact case. Which channels are active is
  decided by which of them the environment configured; configuring none is a
  startup failure, since a triage system that cannot tell anyone anything has
  no reason to run.

## Capabilities

### New Capabilities
- `notification`: what a triage report is as far as delivery is concerned, the
  contract a notification channel satisfies, the guarantee that one channel's
  failure does not suppress another's, the single condition under which
  delivery as a whole has failed, and the requirement that a delivery failure
  is raised rather than disguised as a successful send.

### Modified Capabilities
- `config`: adds notification channel settings to the environment-only side of
  the behavior/connection boundary, and makes the set of active channels a
  consequence of what the environment configured — including the refusal to
  start when it configured none.

## Impact

- New `domain/report.py` carrying `TriageReport`. Stdlib-only, as the domain
  requires.
- New `ports/notifier.py` with the port and `NotifierError` beside it,
  mirroring `AlertSourceError` and `TriageLedgerError`.
- New `adapters/email/` and `adapters/teams/` — both package directories
  already exist as empty placeholders from slice 0 — each owning its channel's
  rendering, its connection settings, and its wire protocol.
- A fan-out notifier composing channel notifiers. It implements the same port
  it consumes, so slice 5 injects one object and never learns how many channels
  are behind it.
- No new runtime dependency: `smtplib`, `email.message`, and `urllib.request`
  are all standard library. `urllib.request` joins the `forbidden_modules` list
  in `pyproject.toml` for symmetry with `smtplib` — the core has no business
  making an HTTP request either.
- No change to `Alert`, `Incident`, `group_alerts`, `triage`, or the two
  existing ports and their adapters. Slice 4 adds an outbound edge; it does not
  reshape anything upstream of it.
- Still nothing wired together — there is no composition root yet. Slice 5 is
  the first consumer of this port, and with it the pipeline becomes runnable
  end to end.
