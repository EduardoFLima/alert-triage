# Adding an adapter

Plugging in your own observability or notification tooling is a first-class
operation. Say you want to notify Slack instead of Teams:

**1. Pick the port you are implementing.** Each port is one seam:

| Port | Implement it to change… |
|---|---|
| `AlertSource` | where alerts come from (Datadog, Prometheus, …) |
| `Investigator` | how an alert group gets investigated |
| `ObservabilityPlatform` | where the investigator queries logs, traces, and metrics for context (Datadog, …) |
| `TriageLedger` | where dedup and cooldown state is kept |
| `Notifier` | where the triage report is delivered |
| `Config` | where configuration is read from |

**2. Create the subpackage.** One directory per integration, named for the
vendor: `src/alert_triage/adapters/slack/`. Your vendor library is a dependency
of that package and of nowhere else — add it to `[project] dependencies` in
`pyproject.toml`, and add it to the `forbidden_modules` list of the vendor
contract in the same file so it can never leak into the core.

**3. Implement the port.** Translate at the boundary: the adapter converts
between the vendor's payloads and the project's own domain types. If you find
yourself wanting to import your SDK from `ports/` or `domain/`, the
architecture test will stop you — that pull is the signal that a domain type is
missing, not that the rule is inconvenient.

**4. Write the tests it must carry.**

- A unit test per translation and per error path, against a fake or stubbed
  client — no network. These are the tests that must exist.
- An integration test in `tests/integration/` if the adapter has wiring worth
  exercising against a running fake.
- No new architecture test: the contracts already cover your subpackage.

**5. Wire it up in `app/`.** The composition root is the only place that names
your adapter. Nothing else in the codebase learns it exists.

**6. Run the gate.** `uv run ruff check src tests && uv run mypy && uv run
pytest`. Green means your adapter is in without having bent the architecture.

## A notification channel

The two existing channels share a shape, and Slack would follow it. Each is
three modules:

```
adapters/slack/
├── notifier.py  renders a TriageReport and delivers it
├── slack.py     the vendor protocol, and the default way to speak it
└── settings.py  resolves the channel from the environment
```

- *Split rendering from sending.* A pure function turns a `TriageReport` into
  your channel's payload; delivery takes the thing that performs the send as an
  injected argument. Keep that seam as narrow as what you actually call — the
  Teams channel needs one function (`Post`), the email channel three methods
  (`SmtpClient`). That is what keeps `tests/unit/` free of a network and a mail
  server, and it is why neither channel's tests subclass a standard-library
  type.
- *Resolve settings from the environment, beside the adapter.* A
  `resolve_slack_settings(env)` returning `None` leaves the channel inactive;
  supplying some of its settings and not the rest raises `ConfigError`. There
  is no `config.yaml` key for a destination or a token, by design — see
  [`configuration.md`](configuration.md).
- *Register it in `resolve_notifier`.* `adapters/fan_out/resolution.py` is the
  one place that decides which channels a deployment has. Add your channel
  there and the fan-out, the partial-failure rule, and the refusal to start
  with no channel all apply to it unchanged.

Raise `NotifierError` for anything that means "not delivered", and never return
quietly on a failure: the caller reads a return as "the team was told" and
starts the re-notify cooldown on it.
