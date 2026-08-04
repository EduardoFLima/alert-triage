## Context

The repo holds `docs/vision.md` and the OpenSpec scaffolding; there is no source
code, no `pyproject.toml`, and no CI. See proposal.md — Why for motivation, and
`specs/project-conventions/spec.md` for the requirements this design satisfies.

Three constraints shape the choices below:

1. **The architecture must survive growth.** `docs/vision.md` commits to ports
   and adapters specifically so the domain never learns about Datadog, ADK, or
   Teams. A convention that is only written down erodes; this design makes the
   boundary a build failure.
2. **The project is meant to be forked and extended publicly.** Setup has to
   work on a stranger's machine from a clone, and adding an adapter has to be an
   obvious, documented operation.
3. **v1 runs from a laptop, later from a container on Cloud Run/GKE.** Whatever
   manages dependencies must produce a reproducible install inside an image, not
   just a working local venv.

## Goals / Non-Goals

**Goals:**

- One import-direction rule, enforced mechanically and reported with a message
  that names the violating import.
- A single canonical agent-instruction file with no duplicated copies to drift.
- A layout where each later slice has an obvious home for its port, its adapter,
  and its tests — no per-slice restructuring debate.
- A CI gate that is the same set of commands a developer runs locally.

**Non-Goals:**

- Defining any port's method signature. The layout reserves the package;
  slice 1+ fills it. Empty packages with a docstring are the deliverable here.
- Container or deployment configuration — that is slice 11. This slice only
  avoids choices that would make containerization awkward.
- Runtime dependencies. No ADK, MCP client, or mail library is added until the
  slice that uses it, so the dependency tree stays legible.

## Decisions

### Enforce the boundary with import-linter, invoked through pytest

Import-linter declares layered and forbidden contracts in `pyproject.toml` and
walks the *transitive* import graph, which is the part that matters: a hand-
rolled check that greps each file's own imports misses `domain → domain.util →
adapters.datadog`. Two contracts cover the rule:

- a `layers` contract ordering `app` → `adapters` → `ports` → `domain`, so
  dependencies may only point inward;
- a `forbidden` contract with `include_external_packages = true`, listing
  `domain` and `ports` as sources and vendor packages as forbidden targets, so
  a port cannot start typing itself against a Datadog SDK model.

The contracts are run from a pytest test rather than only as a standalone CLI
step. That way the rule is part of "the tests pass" for every developer and
every agent, and a violation shows up in the same output as any other failure.

*Alternatives considered:* a custom AST-walking test (zero dependencies, but
transitive analysis is exactly the hard part and re-implementing it is
unjustified); relying on code review (this is the failure mode the slice
exists to prevent); `ruff`'s banned-import rules (per-file only, no notion of
layers, and no transitive reach).

### uv for environment and dependency management

uv resolves and installs fast enough that the CI gate stays cheap, produces a
committed `uv.lock` for reproducible installs, and manages the Python version
itself — so the README's fresh-clone path is `uv sync` rather than a paragraph
about pyenv. It reads standard `[project]` metadata in `pyproject.toml`, so
nothing here is uv-specific if the project later moves off it. Its container
story (`uv sync --frozen --no-dev`) is the one slice 11 will want.

*Alternatives considered:* Poetry (mature, but slower and historically less
standards-aligned in its metadata); pip + `requirements.txt` (no real lockfile
for a shared public repo, and the fresh-clone path becomes multi-step).

### ruff for both lint and format, mypy strict for types

ruff replaces the flake8-plus-black-plus-isort stack with one tool and one
config block, which keeps the gate to three commands. mypy runs in strict mode
from the start: retrofitting strict typing onto an existing codebase is
painful, and this is the only moment when the codebase is empty. Where a
third-party library ships no types, the escape hatch is a narrowly scoped
per-module `ignore_missing_imports` — never a global relaxation.

*Alternatives considered:* pyright (excellent, but Node-based, which adds a
runtime to the CI image and to contributors' machines for no gain here).

### Source layout: `src/alert_triage/{domain,ports,adapters,app}`

`src/` layout ensures tests import the installed package rather than the
working directory, so the packaging that slice 11 relies on is exercised from
day one. Inside it, the four packages map directly onto the diagram in
`docs/vision.md`:

- `domain/` — entities and logic (Alert, grouping, escalation rules). Imports
  nothing but the standard library.
- `ports/` — the abstract interfaces (AlertSource, Investigator, TriageLedger,
  Notifier, Config). Imports `domain` only.
- `adapters/` — one subpackage per vendor integration (`adapters/datadog/`,
  `adapters/adk/`, `adapters/email/`, `adapters/teams/`). Imports `ports` and
  `domain`, plus its own vendor library.
- `app/` — composition root and entrypoint: reads config, constructs concrete
  adapters, injects them into the domain. The only layer that knows every name.

The composition root being the *only* place adapters are named is what makes
the layers contract expressible; scattering construction across the domain
would defeat it.

### Symlinks for harness-specific instruction files

`AGENTS.md` is the real file; `CLAUDE.md` and `GEMINI.md` are git symlinks to
it. Git stores symlinks natively, so a clone on macOS or Linux gets a genuine
link and any edit is instantly visible under all three names — which is exactly
what the spec's "byte-identical content" scenario asks for. A CI assertion
checks the links still resolve to `AGENTS.md`, since a well-meaning editor or a
Windows checkout without `core.symlinks` can silently replace a link with a
copy.

*Alternatives considered:* generating copies from a template via a pre-commit
hook (three real files that can be edited independently — the drift this is
meant to prevent).

### Test layout: `tests/unit/` and `tests/integration/`, split by directory

Directory placement decides scope, with pytest markers applied automatically
per directory rather than hand-annotated on each test. Hand-applied markers get
forgotten; a path cannot be. `tests/unit/` runs with no network and is the loop
developers run constantly; `tests/integration/` holds tests that stand up fakes
or touch real I/O. The architecture contract test lives in `tests/unit/` — it
reads the import graph, nothing external.

### CI runs the same four commands as local development

A single GitHub Actions workflow on push and pull request: `ruff check`,
`ruff format --check`, `mypy`, `pytest`. No CI-only steps and no
locally-unavailable steps, so a green local run predicts a green CI run. The
symlink assertion and the import contract are tests, so they arrive inside
`pytest` rather than as bespoke workflow steps.

## Risks / Trade-offs

- **Strict mypy plus untyped agent/observability SDKs will create friction in
  slices 2 and 6** → the friction is contained to adapters by design; the fix
  is a per-module override in `pyproject.toml` naming the specific library,
  which keeps the domain's strictness intact and makes each exception visible in
  review.
- **Symlinks do not survive a Windows checkout without `core.symlinks=true`** →
  the CI assertion catches a copy that has replaced a link, and the README
  states the requirement. Contributors on Windows are expected to use WSL, which
  the project already implies by targeting containers and GKE.
- **Reserving four packages before any of them has content risks guessing the
  wrong shape** → the shape is not a guess; it is the diagram in
  `docs/vision.md`, and slice 1 will populate `domain` and `ports` immediately,
  so a wrong guess surfaces within one slice rather than after ten.
- **Import-linter is a small-maintainer dependency** → it is dev-only and never
  ships in the runtime image; if it were abandoned, the contracts are ~20 lines
  of declarative config and the enforcement could move elsewhere without any
  source change.
- **An empty repo passing a full quality gate proves little** → true, and
  accepted deliberately: the value is that slice 1 opens with the gate already
  red-lining real violations rather than someone having to install it later.

## Migration Plan

Not applicable — no existing code, consumers, or data. The change is additive
to a repo that currently holds only planning artifacts, and rollback is
deleting the added files.
