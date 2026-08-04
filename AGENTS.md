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

## Hexagonal architecture

The dependency direction is the one rule that must never bend:

```
app  ->  adapters  ->  ports  ->  domain
```

- `domain/` — entities and logic. Imports the standard library and nothing
  else.
- `ports/` — abstract interfaces, expressed in this project's vocabulary.
  Imports `domain` only. A port never types itself against a vendor SDK's
  model; translate at the adapter.
- `adapters/` — one subpackage per integration, each implementing a port and
  owning its vendor library.
- `app/` — the composition root. The only place concrete adapters are named
  and injected.

This is enforced, not reviewed: `tests/unit/test_architecture.py` runs the
import-linter contracts declared in `pyproject.toml` and fails with the
offending module and import named. The contracts walk the *transitive* import
graph, so an indirect route into `adapters` fails too.

**When you add a runtime dependency**, add it to the `forbidden_modules` list
of the "Domain and ports are free of vendor libraries" contract in
`pyproject.toml`. That list is what keeps a new SDK out of the core.

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
```

All four must pass. A green local run is meant to predict a green CI run — if
it does not, fix the discrepancy rather than working around it.

## Planning changes

Non-trivial work is planned through OpenSpec (`openspec/`) before it is
implemented, and `docs/vision.md` is the source of truth for architecture,
ports, and the capability slice order. Reference it; do not copy it into new
documents.
