# Architecture, context by context

The [README](../README.md#architecture) carries the overview: four bounded
contexts, what crosses between them, and the composition root that wires them
up. This is the level below it — each context with the adapters that answer its
ports, one section apiece.

The rules the pictures obey are the same everywhere and are stated once:
dependencies point inward, `adapters` → `ports` → `domain`, and a context never
reaches past another's published contract. Both are enforced by
`tests/unit/test_architecture.py` rather than by review, so a drawing that
disagreed with the code would fail a build.

Every diagram here is an editable SVG. Opening one in [draw.io](https://app.diagrams.net)
gives back the diagram that drew it — the picture and its source are the same
file, so they cannot drift apart.

## Triage — the core

![Triage and its adapters](diagrams/triage.svg)

The only context that owns an aggregate. Alerts arrive, group into incidents by
service and window, and the policy decides what each is owed: whether to
investigate it, whether a report is due, or whether a recent one still holds.

Two ports, two adapters:

- **AlertSource**, answered by the Datadog adapter over the Events API. One
  fixed question on a schedule, wanting a typed answer with real pagination and
  errors that tell "no alerts" apart from "auth rejected".
- **TriageLedger**, answered by SQLite over the standard library's `sqlite3`.
  Durable across processes, transactional, one file to move or delete. It only
  stores; the decision about what is owed stays in the domain.

## Investigation — a target in, a hypothesis out

![Investigation, the crew, and the MCP server](diagrams/investigation.svg)

Reached only through `contract.py`: an `InvestigationTarget` goes in and a
`Diagnosis` comes back. It never learns what an incident is, which is what lets
a contributor write a specialist without meeting triage's aggregate.

The `Investigator` port is answered by the ADK adapter, and behind it sits the
crew:

- **Specialists** — `apm`, `logs`, `trace`, `infrastructure`. Each is a
  declaration rather than a construction: a name, the signal it reports under,
  its instruction, its output schema, the toolsets it may reach, and optionally
  the model it runs on.
- **Reasoners** — the `diagnostician` decides which specialists this incident
  needs and reasons across what they report; the `reporter` formats the result.
  Kept apart so reasoning quality and message wording can be tuned separately.

The specialists reach the Datadog MCP server directly. There is no port over the
observability platform, because MCP is already one — the reasoning is in
[`vision.md`](vision.md#evidence-and-the-platform-boundary).

## Notification — a report, delivered

![Notification and its channels](diagrams/notification.svg)

The most standalone of the three: it knows nothing of incidents or
investigations, only of a `TriageReport`. The `Notifier` port is answered by
both channels at once — a report goes to every configured one, and delivery
counts as successful as soon as one accepts it.

One-way by design, which is what makes acknowledgement an architectural question
rather than a method. See the roadmap in [`vision.md`](vision.md).

## Configuration — what a deployment behaves by

![Configuration and its sources](diagrams/configuration.svg)

Not a peer of the other three but a generic subdomain each of them reads
directly. Two adapters feed it:

- **YAML**, for behaviour — what is watched and how it is triaged.
- **`.env`**, for connection — read once at startup, and only supplementing the
  process environment rather than overriding it.

Which kind a setting is decides which adapter carries it, and every key is
documented in [`configuration.md`](configuration.md).
