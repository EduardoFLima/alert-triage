# Agent instructions

How to work in this repository. This file is about **practices**, not about
what the application does — for that, read the [README](README.md) and
[`docs/vision.md`](docs/vision.md).

This is the only authored instruction file. `CLAUDE.md` and `GEMINI.md` are
symlinks to it; edit `AGENTS.md` and every harness sees the change.

## Test-driven development

Work in red / green / refactor, one cycle per behavior:

1. **Red** — write the smallest test that expresses the next behavior and
   watch it fail. A test that has never failed has not been shown to test
   anything.
2. **Green** — write the least code that makes it pass.
3. **Refactor** — clean up with the test still green.

Tests are not written after the fact and not written in bulk at the end of a
change. If you find yourself writing production code with no failing test
demanding it, stop and write the test.

- `tests/unit/` — no network, no external service, fast. This is the loop you
  run constantly.
- `tests/integration/` — fakes, real I/O, anything with a dependency outside
  the process.
- Scope markers are applied automatically from the directory a test lives in
  (see `tests/conftest.py`); do not hand-annotate `@pytest.mark.unit`.
- Shared fixtures go in the nearest `conftest.py`, not in a helper module that
  tests import.
- Both scope directories mirror the package tree under `src/`, so a module's
  tests are found by the module's own path. Within that structure a file is
  named for the behaviour it establishes, not for the module it exercises — a
  behaviour outlives the file that currently implements it.

## Bounded contexts, each a hexagon

Two rules that must never bend. Inside a context, dependencies point inward.
Between contexts, what one offers another is a published contract, and
everything behind it is private.

```
app  ->  <context>.adapters  ->  <context>.ports  ->  <context>.domain
```

- `triage/` — the core context: alerts, grouping, the Incident aggregate, the
  policy deciding what is owed, and what a report says. The customer of both
  supporting contexts.
- `investigation/` — findings and the agent crew, behind `contract.py`. Its
  adapters split three ways: `crew/` holds the declarations — `specialists/`
  and `reasoners/` as siblings, with `roster.py` saying which exist; `adk/` is
  the framework machinery that turns a declaration into a running agent; and
  `datadog/` is one provider's plumbing, where its server is, how its items are
  addressed, and the grammar its queries are written in. A declaration belongs
  to the crew rather than to a provider, because each of its toolsets names the
  provider serving it and one specialist may name two.
  Its `Investigator` port is declared here, not beside the caller: a port
  belongs to the context whose adapter implements it.
- `notification/` — delivering a report, behind `contract.py`. Genuinely
  standalone: it knows nothing of incidents or investigations.
- `configuration/` — the settings a deployment behaves by. A generic subdomain
  every context may depend on.
- `shared/` — vocabulary more than one context speaks. Depends on no context,
  which is what stops it becoming a dumping ground.
- `app/` — the composition root. The only place concrete adapters are named
  and injected.

Within each context: `domain/` imports the standard library, the shared kernel,
configuration, and the contracts it is entitled to — nothing else. `ports/`
holds abstract interfaces in this project's vocabulary and never types itself
against a vendor SDK's model; translate at the adapter. `adapters/` is one
subpackage per integration, each owning its vendor library.

The permitted cross-context edges are exactly these: `triage` may import
`investigation.contract` and `notification.contract`; neither supporting
context may import the other or reach back into `triage`; every context may
import `shared` and `configuration`; `shared` imports nothing.

This is enforced, not reviewed: `tests/unit/test_architecture.py` runs the
import-linter contracts declared in `.importlinter` and fails with the
offending module and import named. The contracts walk the *transitive* import
graph, so an indirect route into another context's internals fails too.

**When you add a runtime dependency**, add it to the `forbidden_modules` list
of the "Domain and ports are free of vendor libraries" contract in
`.importlinter`, and add its own package to the `source_modules` of that
contract if you have added a context. That list is what keeps a new SDK out of
the core.

**When you add a context**, it needs a layers contract of its own, an entry in
the forbidden contract that keeps the others out of its internals, and its
inner layers added to the vendor-library contract. A contract that has never
been shown to fail has not been shown to enforce anything.

## Clean code

- Names carry the intent; a comment that restates the code is a naming
  failure. Comment *why*, not *what*.
- Small functions, one level of abstraction each, no boolean parameters that
  select behavior.
- Handle errors where there is enough context to decide; do not catch and
  re-raise for decoration.
- Type everything. mypy runs in `strict` mode. If a library ships no types,
  the escape hatch is a per-module override in `pyproject.toml` naming that
  library — never a global relaxation.
- Delete rather than comment out. Git remembers.

## Looking things up

- **Use context7 for library and framework documentation.** ADK, MCP, and the
  observability SDKs move faster than any training data. Look up the current
  API rather than recalling one.
- **Use the mermaid MCP tool for diagrams** added to the README. No
  hand-rolled ASCII, no checked-in images.

## Before you call a change done

Run the same commands CI runs:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy
uv run pytest
docker build -t alert-triage .
```

All five must pass. A green local run is meant to predict a green CI run — if
it does not, fix the discrepancy rather than working around it. The container
tests skip, saying so under `-rs`, where no runtime is available; the build is
what CI never skips.

**When you add a file the run reads at runtime**, check the `Dockerfile`. It
copies by name rather than wholesale — `pyproject.toml`, `uv.lock`, `README.md`,
`LICENSE` and `src/` — so a new file the run needs is absent from the image
unless it is added there, and a new file holding a deployment's own settings
belongs in `.dockerignore` instead. A build context is not a commit: being
gitignored keeps nothing out of an image.

A green run is not the whole story where the change touches a tool name, a
specialist's instruction, or a composed URL. Those are established only against
a real account, by tests that skip silently without credentials — see
[`docs/live-testing.md`](docs/live-testing.md). Say plainly when you have not
run them.

## Planning changes

Non-trivial work is planned through OpenSpec (`openspec/`) before it is
implemented, and `docs/vision.md` is the source of truth for architecture,
ports, and the capability slice order. Reference it; do not copy it into new
documents.
