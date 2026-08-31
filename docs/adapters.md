# Adding an adapter

Plugging in your own tooling is a first-class operation, and it comes in two
shapes. Most of it is a port to implement: a notification channel, the triage
ledger, an alert source. Observability tooling is the exception — there is no platform
port, and you declare [a specialist](#an-observability-specialist) of your own
instead.

So, the port kind first: say you want to notify Slack instead of Teams.

**1. Pick the port you are implementing.** Each port is one seam:

| Port | Implement it to change… |
|---|---|
| `AlertSource` | where alerts come from (Datadog, Prometheus, …) |
| `Investigator` | how an alert group gets investigated |
| `TriageLedger` | where dedup and cooldown state is kept |
| `Notifier` | where the triage report is delivered |
| `Config` | where configuration is read from |

**2. Create the subpackage.** One directory per integration, named for the
vendor, inside the context it serves:
`src/alert_triage/notification/adapters/slack/`. Your vendor library is a
dependency of that package and of nowhere else — add it to
`[project] dependencies` in `pyproject.toml`, and add it to the
`forbidden_modules` list of the vendor contract in `.importlinter` so it can
never leak into the core.

**3. Implement the port.** Translate at the boundary: the adapter converts
between the vendor's payloads and the project's own domain types. If you find
yourself wanting to import your SDK from a context's `ports/` or `domain/`,
the architecture test will stop you — that pull is the signal that a domain
type is missing, not that the rule is inconvenient.

**4. Write the tests it must carry.**

- A unit test per translation and per error path, against a fake or stubbed
  client — no network. These are the tests that must exist.
- An integration test in `tests/integration/` if the adapter has wiring worth
  exercising against a running fake.
- No new architecture test: the contracts already cover your subpackage,
  because they name your context rather than your integration.

**5. Wire it up in `app/`.** The composition root is the only place that names
your adapter. Nothing else in the codebase learns it exists.

**6. Run the gate.** `uv run ruff check src tests && uv run mypy && uv run
pytest`. Green means your adapter is in without having bent the architecture.

## A notification channel

The two existing channels share a shape, and Slack would follow it. Each is
three modules:

```
notification/adapters/slack/
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
- *Register it in `resolve_notifier`.* `app/composition.py` is the
  one place that decides which channels a deployment has. Add your channel
  there and the fan-out, the partial-failure rule, and the refusal to start
  with no channel all apply to it unchanged.

Raise `NotifierError` for anything that means "not delivered", and never return
quietly on a failure: the caller reads a return as "the team was told" and
starts the re-notify cooldown on it.

## An observability specialist

This one is not a port, and the steps above do not apply. There is nothing to
implement and no set of methods to finish before anything runs: a specialist is
one value, declared whole, under the platform it queries:
`investigation/adapters/<platform>/specialists/`. A platform this project has
never reached is a directory of your own beside `datadog/`, holding how its MCP
server is addressed and every specialist declared against it.

| Yours to declare | What it is |
|---|---|
| `name` | what the specialist is called, in the agent and in `config.yaml` |
| `signal` | the dimension its findings are drawn from |
| `instruction` | what it looks for, in your platform's own terms — including its query dialect, which is not translatable |
| `output_schema` | the shape it reports in. It cites what it was shown; there is no field to write evidence into |
| `toolsets` | the toolsets on your platform's MCP server, and the tool names within each that this specialist may reach |
| `model` | optional, where this specialist needs a different model from its siblings |

The deployment supplies the rest — the platform's endpoint, the credentials
that authenticate against it, and the model every specialist reasons on unless
it named its own. None of that is written into a declaration, so the same
specialist runs against another account unchanged.

Copy `investigation/adapters/datadog/specialists/logs.py`, swap its tool names
and its instruction, and add it to the crew in
`investigation/adapters/adk/crew.py`. Its tests are the ones that file
already carries: the instruction asks for what you think it asks for, the
declaration reaches no tool outside it, and its schema builds findings at both
citation grains — all without constructing an agent or reaching a model.

**One specialist is a complete contribution.** It runs, it gathers evidence,
and its findings reach the report on their own; there is no set of four that
must all exist before anything works.

**Adding it to the crew offers it; it does not schedule it.** The diagnostician
decides which specialists each incident needs and consults those, so a new
declaration is available to be chosen rather than guaranteed to run. What gets
it chosen is its `name` and its `instruction` — those are what the manager reads
when deciding — so a specialist named for the signal it covers, whose
instruction says plainly what it looks for, is one that gets asked. A
specialist that never seems to be consulted is usually one whose declaration
does not say what it is for.

**Nothing here checks whether an instruction is any good.** The tests confirm
what a specialist asks for and what it may reach, not whether asking that
produces a useful investigation. Judging that is what the evaluation harness is
for, and it does not exist yet — until it does, a new instruction is worth
running against a real incident and reading the report yourself.

A note on cost: a specialist's spend rises with the number of tools it may
reach, because runtime discovery means the model decides how many calls to
make. Until the circuit breakers are wired to configuration, the re-notify
cooldown is the only thing bounding how often an investigation happens at all.
