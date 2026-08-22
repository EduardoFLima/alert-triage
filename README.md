# Alert Triage

Teams receive Datadog alerts and ignore them — not because the alerts are
wrong, but because responding takes time and troubleshooting knowledge nobody
has in the moment. Alert Triage is a recurring job that watches for recent
alerts, does the first-pass investigation a knowledgeable human would do, and
sends the team a triage report.

It does the legwork and presents a hypothesis with its confidence. It does not
auto-remediate and does not decide for you: the question left to a human is
"act on this?" rather than "where do I even start?"

The full product vision and capability roadmap live in
[`docs/vision.md`](docs/vision.md); the settings reference is in
[`docs/configuration.md`](docs/configuration.md).

> **Status:** end to end, before investigation. A run fetches alerts, groups
> them, keeps a ledger so a team is told once per incident, and delivers a
> report — but the report is a pass-through of the alerts, and says so. The
> investigation that fills it in is the next capability slice.

## Setup

**Prerequisites**

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — manages the
  Python version and the virtual environment, so no prior Python setup is
  needed.
- git with symlink support. macOS and Linux have it by default; on Windows use
  WSL, or clone with `git clone -c core.symlinks=true`.

**Install**

```bash
git clone https://github.com/EduardoFLima/alert-triage.git
cd alert-triage
uv sync
```

`uv sync` reads the committed `uv.lock`, so the versions you get are the
versions CI gets.

**Verify**

```bash
uv run pytest
```

A passing run means the environment is working, the package installed
correctly, and the architecture boundary holds.

**Configure**

`scope.owner` is the only mandatory behavior setting, and at least one
notification channel must be configured or the run refuses to start:

```bash
export SCOPE_OWNER=sre                                     # whose alerts are triaged
export ALERT_TRIAGE_TEAMS_WEBHOOK_URL=https://prod-1...    # where reports go
export DD_API_KEY=...                                      # and DD_APP_KEY
```

That is enough for a first run. Everything else has a documented default.

Rather than exporting by hand, copy the two annotated examples and edit them —
every key and every variable is listed there with its default:

```bash
cp config.example.yaml config.yaml   # behavior; safe to commit
cp .env.example .env                 # connection; gitignored, never committed
```

A `.env` file beside the run is read at startup and only *supplements* the
environment: anything the process already exported wins, so a container or a
scheduler is never overridden by a file lying next to it.

Which kind a setting is decides where it goes: *behavior* — what the system
watches and how it triages — lives in an optional `config.yaml`, while
*connection* — credentials, the ledger's location, where reports are sent — is
read from the environment only, so a config file stays portable and never grows
a key shaped like a credential.

The full reference — every key, every variable, the defaults, and how delivery
behaves when one channel fails — is in
[`docs/configuration.md`](docs/configuration.md).

## Running it

A run is one pass — fetch the recent alerts, group them, decide what each
group belongs to, report what is due, record what it handled — and then the
process exits. There is no daemon and no loop: something else decides how
often a run happens.

```bash
uv run alert-triage      # from a checkout
alert-triage             # wherever the package is installed
python -m alert_triage   # the same job, without the console script
```

A run reads everything it needs from its environment:

- `SCOPE_OWNER` — whose alerts are in scope. Mandatory, and the one setting
  that may instead live in `config.yaml`.
- `DD_API_KEY` and `DD_APP_KEY` — the Datadog credentials the fetch
  authenticates with. `DD_SITE` if the account is not on `datadoghq.com`.
- `GOOGLE_API_KEY` — what the model an investigation reasons on costs to
  reach. A deployment on the enterprise platform sets
  `GOOGLE_GENAI_USE_ENTERPRISE=true` instead and needs no key.
- At least one notification channel, or the run refuses to start rather than
  fetching alerts it could tell nobody about.
- `ALERT_TRIAGE_LEDGER_PATH` — where the incidents on record are kept.
  Defaults to `data/alert_triage.db` under the working directory, which is why a
  deployment should set it explicitly.

The run's account of itself goes to stderr; what it did goes in its exit
status, which is what a scheduler acts on:

- `0` — every group the run fetched was decided, reported if it was due, and
  recorded. A run that had nothing to report succeeds having delivered
  nothing.
- `1` — the deployment is unusable, the fetch failed, or at least one group
  could not be reported or recorded. The log names the stage that failed and
  the service it was handling; the groups that succeeded still got their
  reports.

## Development

The four commands below are exactly what CI runs — nothing more, nothing
CI-only:

```bash
uv run ruff check src tests      # lint
uv run ruff format --check src tests
uv run mypy                      # strict type checking
uv run pytest                    # full suite, with coverage
```

Useful selections while working:

```bash
uv run pytest -m unit            # fast set: no network, no external service
uv run pytest -m integration     # integration-scope tests only
uv run ruff format src tests     # apply formatting
```

Engineering practices — TDD, clean code, the import rule — are in
[`AGENTS.md`](AGENTS.md), which applies to humans and coding agents alike.

## Architecture

Hexagonal (ports and adapters). The domain does not know which agent framework
or which notification channel it is talking to — those are adapters behind
ports. That is what makes the tool forkable for your own tooling, and what lets
it run locally, in a container, or on Cloud Run without the core changing.

There is deliberately no port over the observability platform. A specialist
reaches the platform's own MCP toolset, filtered to the tools that specialist
declared, and every result crosses an evidence callback on the way back — which
is what makes a citation checkable and what stops a failed retrieval from
reading as a service with nothing to say. Why that boundary sits at MCP rather
than in a hand-written abstraction is argued in
[`docs/vision.md`](docs/vision.md#evidence-and-the-platform-boundary).

```mermaid
flowchart TB
    subgraph InboundAdapters["adapters — inbound"]
        direction TB
        DatadogREST["AlertSource Adapter<br/>Datadog REST"]
    end
    subgraph InboundPorts["ports — inbound"]
        direction TB
        AlertSource["AlertSource"]
    end
    subgraph Domain["domain — entities and logic"]
        direction LR
        Alert["Alert"] --> Grouper["Grouper"]
        Grouper --> Ledger["dedup / cooldown"]
        Grouper --> Investigation["Investigation"]
        Investigation --> Diagnosis["Hypothesis + confidence"]
        Diagnosis --> Report["Triage report"]
        Report --> Escalation["Escalation<br/>(side channel)"]
    end

    subgraph OutboundPorts["ports — outbound"]
        direction LR
        Investigator["Investigator Agent"] ~~~ TriageLedger["Triage Ledger"] ~~~ Notifier["Report Notifier"] ~~~ Config["Config Reader"]
    end

    subgraph OutboundAdapters["adapters — outbound"]
        direction LR
        ADK["Investigator Adapter<br/>Google ADK crew"] ~~~ TriageLedgerAdapter["Triage Ledger Adapter<br/>SQLite"] ~~~ NotifierEmailAdapter["Notifier Adapter<br/>Email"] ~~~ NotifierTeamsAdapter["Notifier Adapter<br/>Teams"] ~~~ ConfigAdapter["Config Adapter<br/>YAML"]
    end

    subgraph Investigating["inside the investigator adapter"]
        direction TB
        Declaration["Specialist declaration<br/>signal · instruction · schema · tools"]
        Toolset["Filtered MCP toolset<br/>only the declared tool names"]
        Evidence["Evidence callback<br/>keeps what came back,<br/>refuses what failed"]
        Declaration --> Toolset
        Toolset --> Evidence
        Evidence --> Declaration
    end

    DatadogREST -. implements .-> AlertSource
    AlertSource --> Domain
    Domain ---> OutboundPorts
    OutboundPorts ---> OutboundAdapters
    ADK --> Declaration
    Toolset --> PlatformMCP[("Platform MCP server<br/>Datadog")]

    classDef domainClass fill:#fdf6e3,stroke:#c9a227,color:#3a2f00
    classDef portsClass fill:#eef0fb,stroke:#5b63d3,color:#1a1a2e
    classDef adaptersClass fill:#eaf6ec,stroke:#3f9142,color:#123a17
    classDef platformClass fill:#f6ecec,stroke:#a23f3f,color:#3a1212

    class Domain domainClass
    class InboundPorts,OutboundPorts portsClass
    class InboundAdapters,OutboundAdapters,Investigating adaptersClass
    class PlatformMCP platformClass
```

Dependencies point inward only — `adapters` → `ports` → `domain` — and that
direction is enforced by `tests/unit/test_architecture.py`, not by review. The
composition root (`app/`) wires adapters into ports at startup; it has no
runtime dependency edge of its own.

```
src/alert_triage/
├── domain/      entities and logic; standard library only
├── ports/       interfaces; imports domain only
├── adapters/    one subpackage per integration, each owning its vendor library
│   ├── datadog/
│   ├── sqlite_ledger/
│   ├── adk/
│   ├── email/
│   ├── teams/
│   └── fan_out/ one Notifier standing for every configured channel
└── app/         composition root: the only layer that names concrete adapters

tests/
├── unit/        no network, no external service
└── integration/ fakes and real I/O
```

## Extending it

Two kinds of extension, and they have different shapes.

**A notification channel is a port to implement.** Pick the port, create a
subpackage owning your vendor library, translate at the boundary, and register
it in `app/`. The step-by-step guide — including the extra conventions a
channel follows — is in [`docs/adapters.md`](docs/adapters.md).

**Observability tooling is a specialist to declare.** There is no platform port
to implement and no set of methods to finish first. A specialist is one value
in `adapters/adk/`, declared whole:

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

Copy `adapters/adk/logs_agent.py`, swap its tool names and its instruction, and
add it to the crew in `adapters/adk/crew.py`. Its tests are the ones that file
already carries: the instruction asks for what you think it asks for, the
declaration reaches no tool outside it, and its schema builds findings at both
citation grains — all without constructing an agent or reaching a model.

**One specialist is a complete contribution.** It runs, it gathers evidence,
and its findings reach the report on their own; there is no set of four that
must all exist before anything works.

**Nothing here checks whether an instruction is any good.** The tests confirm
what a specialist asks for and what it may reach, not whether asking that
produces a useful investigation. Judging that is what the evaluation harness is
for, and it does not exist yet — until it does, a new instruction is worth
running against a real incident and reading the report yourself.

A note on cost: a specialist's spend rises with the number of tools it may
reach, because runtime discovery means the model decides how many calls to
make. Until the circuit breakers are wired to configuration, the re-notify
cooldown is the only thing bounding how often an investigation happens at all.

## License

See [LICENSE](LICENSE).
