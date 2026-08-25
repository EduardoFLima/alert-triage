## Context

The layering in `docs/vision.md` is intact and machine-enforced; what has aged
is the taxonomy inside it. See proposal.md — Why.

Two facts shape every decision below. First, `Investigator.investigate` takes
an `Incident` and returns `Findings`, and `TriageReport` holds an `Incident` —
so splitting the code into contexts along the obvious seams produces import
cycles unless something is done about the types that cross. Second, the crew
reads exactly three things off an incident (`service`, `window`, and the
*count* of alerts), and only tests read `report.incident` — so the cost of
doing something about them is small, and it is smaller now than after slices
9–10 multiply the call sites.

## Goals / Non-Goals

**Goals:**

- One hexagon per bounded context, with cross-context edges that are few,
  directed, and named.
- Every move mechanical enough to review, and the suite green at every step.
- A tree in which slice 8's evaluation harness and slices 9–10's five new
  specialists have an obvious home before they are written.

**Non-Goals:**

- Changing any runtime behaviour. Identical inputs produce identical reports,
  identical ledger rows, and identical exit codes.
- Rewriting `README.md`'s prose. Its diagram and adapter guide are updated to
  match the new tree; the document is not otherwise revisited.
- Consolidating the per-adapter environment settings modules.

## Target layout

```
src/alert_triage/
├── shared/window.py
├── configuration/    settings.py  port.py  adapters/{yaml,env_file}
│
├── triage/           domain/    incident alert grouping policy report
│                     ports/     alert_source ledger investigation
│                     adapters/  datadog/{connection,alert_source}  sqlite/
│
├── investigation/    contract.py    InvestigationTarget, Findings, Finding,
│                                    EvidenceItem, Signal
│                     domain/    specialist  evidence
│                     adapters/  adk/       (framework)
│                                datadog/   (platform: mcp + specialists)
│
├── notification/     contract.py    TriageReport
│                     ports/notifier.py
│                     adapters/ email/  teams/  fan_out.py
│
└── app/              composition.py  pipeline.py  main.py
```

## Decisions

**Bounded contexts as the top-level split.** The alternative was to keep the
global layer folders and group `adapters/` by the port each implements. That
answers "who implements `Notifier`" but leaves investigation's subsystem as one
entry in a flat list, which is the actual complaint. Contexts also give the
evaluation harness and the five coming specialists somewhere to go. Splitting
`domain/` by entity/value-object/service stereotype was considered and
rejected: it would scatter `Incident`, `Alert`, and `Window` across three
folders and hide the aggregate boundary, which is the line worth making
visible, while `entities/` would hold exactly one file.

**Two anticorruption layers instead of a shared model.** `InvestigationTarget`
(`service`, `window`, `alert_count`) replaces `Incident` at the investigation
boundary, and `TriageReport` drops its `Incident` field for `incident_id` and
`service`. The alternative — declaring `Incident` a shared kernel — is cheaper
today and unbounded tomorrow, because a shared aggregate grows until the
contexts are not separate. It also serves the contributor story in
`docs/vision.md` directly: someone writing a specialist for another platform
reads a four-field record, not this project's aggregate.

**Triage is the customer of both supporting contexts.** Rather than each
context importing whatever it needs, the permitted edges are enumerated:
`triage` may import `investigation.contract` and `notification.contract`;
neither supporting context may import the other or reach back into `triage`;
every context may import `shared` and `configuration`; `shared` imports
nothing. This keeps `notification` genuinely standalone — the reason
`build_report` stays in `triage`, which is where deciding what to say about an
incident belongs, while delivering it belongs to `notification`.

**A shared kernel holding `Window` and nothing else.** `Window` appears inside
a domain type on both sides (`Incident.window`, `InvestigationTarget.window`),
so duplicating it would duplicate its invariant, and assigning it to either
context would make the other import across a boundary for a time primitive.
The guard against `shared/` becoming a dumping ground is a contract rather than
discipline: it may import no context, so anything with a context-specific
dependency cannot be added to it.

**`configuration` is a generic subdomain every context may depend on.** It
holds the nine settings value objects extracted from `ports/config.py`, the
`Config` protocol that was the only port among them, the YAML and env-file
adapters, and `ConfigError`. Treating it as a fifth peer context with a
published contract was considered and rejected as ceremony: nothing reads
configuration except to be configured by it, and a startup refusal is not
domain vocabulary.

**Datadog splits by the two concerns it already serves, translated at the
composition root.** `connection.py` and `alert_source.py` go to
`triage/adapters/datadog/`; the MCP endpoint and headers go to
`investigation/adapters/datadog/mcp.py` and take `site`, `api_key`, and
`app_key` as strings rather than the `DatadogConnection` type, so no
cross-context import appears. `app/composition.py` resolves the connection
once and hands those strings across. Two alternatives were rejected: a
top-level module for vendor connection facts, which would hold one vendor's
variables and invite the question "why not the other four" at every reading;
and letting each context resolve `DD_*` for itself, which costs about the same
and breaks the guarantee `datadog_mcp.py` documents — that a deployment able
to fetch alerts is able to investigate them.

**Investigation's adapters split by framework and by platform.** `adk/` holds
the agent machinery — crew, model, credentials, callbacks, normalisation —
and `datadog/` holds the MCP connection and the specialist declarations, whose
tool names are Datadog's. The alternative, one `adk/` package, mixes two
orthogonal axes and would put five more specialists beside `crew.py` and
`model.py`. The split makes the extension story in `docs/vision.md`
structural: another platform is another directory, not edits threaded through
a shared one.

**Tests mirror the source packages; files are named for behaviour.** Mirroring
at the file level was rejected because it would trade good test names for
module names — `test_investigation_arc.py` says more than `test_run.py` — and
because a behaviour outlives the module that currently implements it.
Mirroring at the package level gets what the flat directory lost: a module's
tests found by its path, a missing test package visible by absence, and
`conftest.py` fixtures scoped to the context that needs them.

## Contract set

The three current contracts become, in `pyproject.toml`:

| Contract | Type | What it holds |
|---|---|---|
| Layers, per context ×4 | `layers` | `adapters` → `ports` → `domain` inside each context |
| Contexts do not reach past contracts | `forbidden` | each context's `domain`/`adapters` unreachable from the others |
| Supporting contexts are independent | `independence` | `investigation` and `notification` never meet |
| Shared kernel depends on nothing | `forbidden` | `shared` may not import any context |
| Domain and ports are free of vendor libraries | `forbidden` | as today, re-pointed at the new module paths |
| The run takes adapters, it does not name them | `forbidden` | as today, `app.pipeline` |

## Migration Plan

Sequenced so that `uv run ruff check`, `ruff format --check`, `mypy`, and
`pytest` all pass after every step, and so that the semantic changes are
separated from the bulk moves that would otherwise hide them:

1. **Semantic changes first, in the current tree.** `TriageReport` loses its
   `Incident` field; `InvestigationTarget` is introduced and the investigator
   port retyped; `mcp_endpoint`/`mcp_headers` retyped to strings and the
   translation lifted into `composition.py`. Each is a red/green cycle with
   its own test, and each is reviewable on its own.
2. **`ports/config.py` splits** into settings and protocol.
3. **Moves**, one context at a time, with `git mv` so rename detection keeps
   blame intact. After each context lands, the full gate runs.
4. **Contracts rewritten** in `pyproject.toml`. Each new contract is first
   shown to fail against a deliberate violation, then to pass — a contract
   that has never failed has not been shown to enforce anything.
5. **Tests move** into the mirrored tree, `conftest.py` fixtures pushed down to
   the contexts that use them.
6. **`README.md`** diagram regenerated and the adapter guide repointed.

Rollback is `git revert` of whichever step failed; no step leaves a
half-migrated tree, because each ends on a green gate.

## Risks / Trade-offs

- **A diff touching every file is review-hostile** → Step 1 carries every
  behaviour-affecting edit and touches few files; steps 3 and 5 are pure
  `git mv` plus import rewrites, which review as mechanical because they are.
- **In-flight work conflicts with a wholesale move** → Slice 7 merged and slice
  8 has not started, which is the widest quiet window this change will get.
  Doing it now is part of the rationale, not an accident of timing.
- **`InvestigationTarget` may prove too thin for later specialists** → It
  carries every piece of alert data that exists today; `Alert` holds only
  `service`, `fired_at`, and `source_id`. If alerts grow richer, the target is
  where that detail lands, and adding a field to it is a one-line change plus
  its translation.
- **New contracts could be written so loosely they never fail** → Step 4
  requires a demonstrated red before the green, the same discipline the
  existing architecture test was built under.
- **Losing `report.incident` removes something a future report might want** →
  Only tests read it, and the two that do are asserting on identity, which
  `incident_id` states more directly. Slice 10 moves report formatting to an
  agent, so a report holding a whole aggregate would be growing the wrong way.
