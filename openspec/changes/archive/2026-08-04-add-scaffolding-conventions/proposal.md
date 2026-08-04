## Why

The repo currently holds planning material and no code. Slice 0 of the
capability slices in `docs/vision.md` exists so every later slice lands in a
structure that already enforces the project's non-negotiables — hexagonal
boundaries, TDD, one canonical agent-instruction file. Establishing those
after code exists means retrofitting them against a codebase that has already
drifted.

## What Changes

- **Agent instructions**: add canonical `AGENTS.md` covering practices only
  (clean code, TDD red/green/refactor, hexagonal architecture, context7 for
  library docs, mermaid MCP for diagrams). `CLAUDE.md` and `GEMINI.md` become
  symlinks to it rather than copies.
- **README skeleton**: setup instructions, a placeholder for the mermaid
  architecture diagram, and the section outline for the "adding a new adapter"
  guide that later slices fill in.
- **Hexagonal package layout**: create the `domain` / `ports` / `adapters` /
  `app` package tree with the import direction that later slices must respect.
- **Python toolchain**: `pyproject.toml` managed by uv (lockfile committed),
  with ruff (lint + format), mypy (strict), and pytest configured.
- **Test harness**: pytest layout with unit/integration separation, shared
  fixtures location, and coverage reporting wired up.
- **Architecture fitness test**: an automated test that fails when `domain` or
  `ports` import from `adapters` or from any third-party integration library —
  the hexagonal rule enforced by CI, not by review discipline.
- **CI gate**: a GitHub Actions workflow running lint, format check, typecheck,
  and the full test suite on push and pull request.

No application behavior ships in this slice — there is no alert to ingest, no
adapter to call. The deliverable is the structure and the gates.

## Capabilities

### New Capabilities

- `project-conventions`: the repo's own enforceable rules — the hexagonal
  import boundary that fails CI when violated, the single-source agent
  instruction file with harness-specific symlinks, and the quality gate every
  change must pass before merge. These are requirements with real tests, not
  documentation preferences.

### Modified Capabilities

<!-- None. This is the first capability in the repo; openspec/specs/ is empty. -->

## Impact

- **New files**: `AGENTS.md`, `CLAUDE.md` + `GEMINI.md` (symlinks), `README.md`,
  `pyproject.toml`, `uv.lock`, `.gitignore`, `.github/workflows/ci.yml`, and the
  source/test package trees.
- **Dependencies introduced**: uv, ruff, mypy, pytest, pytest-cov. No runtime
  dependencies yet — ADK, MCP, and notification libraries arrive with the slices
  that need them.
- **Downstream**: every subsequent slice (1–11) is built inside this layout and
  is subject to these gates. The import-boundary test is the mechanism that
  keeps the architecture in `docs/vision.md` intact as the codebase grows.
- **Existing planning assets**: `docs/vision.md` and `openspec/` are unaffected;
  this slice adds around them.
