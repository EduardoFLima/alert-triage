## 1. Toolchain and project metadata

- [x] 1.1 Initialize the project with uv: create `pyproject.toml` with `[project]`
  metadata (name `alert-triage`, pinned `requires-python`) and a `src/` layout
  build target; commit the generated `uv.lock`
- [x] 1.2 Add dev dependencies only — ruff, mypy, pytest, pytest-cov,
  import-linter — leaving runtime dependencies empty until the slice that needs
  them
- [x] 1.3 Configure ruff (lint rule selection + formatter) and mypy (strict) in
  `pyproject.toml`; confirm `uv run ruff check`, `uv run ruff format --check`,
  and `uv run mypy` all execute cleanly on the empty tree
- [x] 1.4 Add `.gitignore` covering the venv, caches, coverage output, and build
  artifacts

## 2. Package layout

- [x] 2.1 Create `src/alert_triage/` with `domain/`, `ports/`, `adapters/`, and
  `app/` packages, each with an `__init__.py` whose docstring states that layer's
  allowed dependency direction
- [x] 2.2 Create the adapter subpackages reserved by `docs/vision.md` —
  `adapters/datadog/`, `adapters/adk/`, `adapters/email/`, `adapters/teams/` —
  as empty packages
- [x] 2.3 Verify the package imports from an installed environment (`uv run python
  -c "import alert_triage"`), confirming the `src/` layout is wired correctly

## 3. Test harness

- [x] 3.1 Create `tests/unit/` and `tests/integration/` with a root `conftest.py`
  that applies the `unit` / `integration` marker automatically based on a test's
  directory
- [x] 3.2 Configure pytest in `pyproject.toml`: testpaths, marker registration,
  strict markers, and coverage reporting
- [x] 3.3 Add a smoke test asserting the package imports, and confirm
  `uv run pytest -m unit` selects only the unit directory while `uv run pytest`
  runs everything

## 4. Architecture boundary enforcement

- [x] 4.1 Write failing tests first: temporary fixture modules that violate the
  boundary (a `domain` module importing `adapters`, a `ports` module importing a
  vendor package) and assert the contract check reports them
- [x] 4.2 Configure import-linter in `pyproject.toml` — a `layers` contract
  ordering `app` → `adapters` → `ports` → `domain`, and a `forbidden` contract
  with `include_external_packages = true` barring vendor packages from `domain`
  and `ports`
- [x] 4.3 Add `tests/unit/test_architecture.py` that runs the contracts and fails
  with the offending module and import named in the output
- [x] 4.4 Confirm both directions: the violation fixtures fail the check, then
  remove them and confirm the clean tree passes
  (spec: "Hexagonal import boundary is machine-enforced")

## 5. Agent instructions

- [x] 5.1 Write canonical `AGENTS.md` covering practices only — clean code, TDD
  red/green/refactor, hexagonal architecture with the import rule, context7 for
  current library docs, mermaid MCP for README diagrams — with no restatement of
  what the application does
- [x] 5.2 Create `CLAUDE.md` and `GEMINI.md` as git symlinks to `AGENTS.md` and
  verify git recorded them as symlinks, not copies
- [x] 5.3 Add `tests/unit/test_agent_instructions.py` asserting each
  harness-specific filename is a symlink resolving to `AGENTS.md`
  (spec: "Agent instructions have a single source of truth")

## 6. README

- [x] 6.1 Write the setup section: prerequisites, clone, `uv sync`, and the
  verification command that runs the test suite
- [x] 6.2 Generate the architecture diagram with the mermaid MCP tool from the
  structure in `docs/vision.md` and embed it
- [x] 6.3 Write the "adding an adapter" guide: which port to implement, where the
  implementation goes, and the tests it must carry
  (spec: "Contributors can set up and verify the project from the README")
- [x] 6.4 Walk the setup steps from a clean clone in a scratch directory and
  confirm they reach a passing test run without undocumented steps

## 7. CI gate

- [x] 7.1 Add `.github/workflows/ci.yml` running on push and pull request:
  checkout with symlinks preserved, install uv, `uv sync --frozen`, then
  `ruff check`, `ruff format --check`, `mypy`, and `pytest`
- [x] 7.2 Confirm the gate fails as expected by pushing a deliberate lint error, a
  type error, and a boundary violation on a scratch branch, then reverting
  (spec: "Quality gate runs on every change")
- [ ] 7.3 Confirm the gate passes green on the finished branch

## 8. Wrap-up

- [x] 8.1 Run the full local gate one final time and record the output
- [x] 8.2 Run `openspec validate --strict` on this change
