## 1. The report and the port

- [x] 1.1 Write failing tests for a `TriageReport` carrying the incident it
      concerns, a single-line subject, and a plain-text body — including that
      it exposes the incident's identifier and service, and that it carries no
      channel formatting of its own (specs/notification - A triage report is
      channel-neutral)
- [x] 1.2 Implement `domain/report.py` to pass them, stdlib-only and depending
      on nothing beyond `Incident`
- [x] 1.3 Write a failing test that a `Notifier` implementation is recognised
      by the port and that `NotifierError` is importable from the port module,
      not from any adapter (specs/notification - A delivery failure is
      recognisable without knowing the channel)
- [x] 1.4 Implement `ports/notifier.py`: a synchronous `deliver` taking one
      `TriageReport`, with `NotifierError` defined beside it, matching the
      docstring conventions of `ports/alert_source.py` and
      `ports/triage_ledger.py`

## 2. Email channel

- [x] 2.1 Write a failing test that rendering a report produces a message whose
      subject is the report's subject, whose body is the report's body, and
      whose sender and recipients are the configured ones (specs/notification -
      Email delivery)
- [x] 2.2 Implement the pure rendering half in `adapters/email/`, using
      `email.message.EmailMessage`
- [x] 2.3 Write a failing test that delivery submits the rendered message
      through an injected SMTP client, with STARTTLS attempted and credentials
      used when configured (specs/notification - A report is emailed)
- [x] 2.4 Write failing tests that a refused message and an unreachable server
      each raise `NotifierError`, naming what was refused (specs/notification -
      The mail server refuses the message, The destination rejects the report)
- [x] 2.5 Implement the sending half, taking the SMTP client as a factory
      argument so `tests/unit/` needs no mail server, and applying the fixed
      timeout from design.md
- [x] 2.6 Add a test asserting the standard library's `email` package is what
      the adapter imports, despite the adapter's own package being named
      `email`

## 3. Email connection settings

- [x] 3.1 Write failing tests: the SMTP settings resolve from the environment,
      the port defaults when unset, and a value written into `config.yaml` is
      ignored (specs/config - Notification channel settings come from the
      environment, Channel settings written into the config file)
- [x] 3.2 Write failing tests that a half-configured channel is a `ConfigError`
      naming the missing setting — a host with no sender, a host with no
      recipients, a password with no username (specs/config - A channel
      configured only in part)
- [x] 3.3 Implement the resolver beside the adapter, following
      `adapters/datadog/connection.py` and
      `adapters/sqlite_ledger/location.py`

## 4. Teams channel

- [x] 4.1 Look up the current Workflows incoming-webhook envelope and Adaptive
      Card schema version with context7 before writing the renderer, per
      `AGENTS.md` — the shape in design.md is to be confirmed, not assumed
- [x] 4.2 Write a failing test that rendering a report produces the confirmed
      message envelope with the subject as the card's heading and the body as
      its text (specs/notification - Microsoft Teams delivery)
- [x] 4.3 Implement the pure rendering half in `adapters/teams/`
- [x] 4.4 Write a failing test that delivery POSTs the rendered JSON to the
      configured webhook URL through an injected opener, and treats a 2xx as
      success (specs/notification - A report reaches a Teams channel)
- [x] 4.5 Write failing tests that a non-2xx response and a transport error
      each raise `NotifierError` carrying the status and response body
      (specs/notification - Teams rejects the post)
- [x] 4.6 Implement the sending half over `urllib.request`, with the fixed
      timeout from design.md
- [x] 4.7 Write failing tests that the webhook URL resolves from the
      environment and is ignored when written into `config.yaml`, then
      implement the resolver (specs/config - A webhook URL is never a config
      file key)

## 5. Fan-out

- [x] 5.1 Write a failing test that a report is delivered to every configured
      channel exactly once (specs/notification - Every channel is attempted)
- [x] 5.2 Write a failing test that a channel failing does not stop a later
      channel from being attempted (specs/notification - The first channel
      fails)
- [x] 5.3 Write a failing test that delivery succeeds when at least one channel
      accepted the report, and that the failures of the others are logged
      rather than discarded (specs/notification - Partial delivery is a
      success, A failure that reached nobody is not hidden)
- [x] 5.4 Write a failing test that delivery raises `NotifierError` when every
      channel failed, and that the raised error accounts for each channel's own
      failure rather than only the last (specs/notification - No channel
      accepts the report, The failure accounts for every channel)
- [x] 5.5 Write a failing test that no channel is attempted more than once for
      one report (specs/notification - A failing channel is not retried in
      place)
- [x] 5.6 Implement the fan-out notifier, itself satisfying the `Notifier` port
      so a caller cannot tell how many channels sit behind it

## 6. Channel resolution

- [x] 6.1 Write failing tests that the active channels follow what the
      environment configured: email alone, Teams alone, and both
      (specs/config - Only one channel configured, Both channels configured)
- [x] 6.2 Write a failing test that configuring no channel at all raises
      `ConfigError`, in the same manner as a missing scope or credential
      (specs/config - No channel configured, The refusal is a configuration
      error like any other)
- [x] 6.3 Implement the resolver that assembles the fan-out notifier from the
      environment

## 7. Boundaries and closing out

- [x] 7.1 Add `urllib.request` to the `forbidden_modules` list of the "Domain
      and ports are free of vendor libraries" contract in `pyproject.toml`, and
      confirm `tests/unit/test_architecture.py` still passes
- [x] 7.2 Add an integration test in `tests/integration/` that sends a real
      message through a local SMTP debugging server, and one that posts to a
      local HTTP server standing in for the webhook — real I/O, no external
      service
- [x] 7.3 Update the README with the notification environment variables and
      what activates each channel, and extend the "adding an adapter" guide to
      cover a notification channel
- [x] 7.4 Run `uv run ruff check src tests`, `uv run ruff format --check src
      tests`, `uv run mypy`, and `uv run pytest`, and confirm all four pass
