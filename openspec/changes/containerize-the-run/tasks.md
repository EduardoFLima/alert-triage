## 1. Reword the slice before building it

- [x] 1.1 Rewrite slice 14 in `docs/vision.md` to be containerization only —
      drop "then Cloud Run/GKE manifests", state `docker run` as the deployment
      story, and say that a hosted target is a later decision this image is the
      prerequisite for
- [x] 1.2 Rewrite the `## Deployment` section of `docs/vision.md` to match:
      v1 runs manually, next step is the image, and GCP is a possible later
      landscape rather than the stated next step
- [x] 1.3 Fix slice 15's forward reference, which currently says slice 14
      "introduces a deployment story a reader will want to see" and names Cloud
      Run/GKE by implication — the diagram rework still has something to absorb,
      but it is an image rather than a hosted topology

## 2. The container test harness

- [x] 2.1 Add a `tests/integration/deployment/` package mirroring nothing under
      `src/` — packaging is a property of the distribution, so it sits beside
      `test_installed_distribution.py`'s concern rather than under a module path
- [x] 2.2 Add a `conftest.py` there with the skip gate: a fixture that finds
      `docker` on the path and confirms the daemon answers, skipping with the
      reason named when either is absent
- [x] 2.3 Add an `image` fixture resolving the tag from an environment variable
      with a documented default, building it once per session when absent, and
      failing loudly rather than skipping when a build is attempted and fails
- [x] 2.4 Confirm the gate works both ways: the suite passes with `docker`
      unavailable and reports the skips under `pytest -rs`

## 3. The image performs a run

- [x] 3.1 **Red** — a test that runs the image with an environment holding no
      scope and asserts it exits non-zero naming `scope.owner`. It fails because
      there is no Dockerfile
- [x] 3.2 **Green** — the smallest `Dockerfile` that passes it: a base image,
      the project installed, `ENTRYPOINT ["alert-triage"]` in exec form
- [x] 3.3 **Refactor** — split into build and runtime stages, install with
      `uv sync --locked --no-dev --no-editable` into a virtualenv the runtime
      stage copies, per `design.md`
- [x] 3.4 **Red/Green** — a test that a fully configured run reaches the fetch
      and fails there, naming the stage, rather than failing on anything the
      image got wrong. This is the test that catches a missing dependency or an
      unconstructible adapter
- [x] 3.5 **Red/Green** — a test that no argument-free start is needed: assert
      the image declares no `CMD` that an appended argument would replace

## 4. What the image must not carry, and who it runs as

- [x] 4.1 **Red** — a test asserting the built image contains no `.env`, no
      `config.yaml`, no `data/` and no virtualenv from the checkout. It fails
      against a build with no ignore file
- [x] 4.2 **Green** — a `.dockerignore` covering environment files, the ledger
      directory, virtualenvs, caches, `.git`, and `.claude/`
- [x] 4.3 **Red/Green** — a test that the development tooling is absent from the
      image (no pytest, ruff, mypy or import-linter in the runtime virtualenv)
- [x] 4.4 **Red/Green** — a test that the run's process is owned by a non-root
      user; add the fixed UID/GID user to the Dockerfile to pass it
- [x] 4.5 **Red/Green** — a test that a stale lockfile fails the build rather
      than resolving a different set, exercised by building with a deliberately
      disagreeing `pyproject.toml` and asserting a non-zero build

## 5. The history outlives the container

- [x] 5.1 **Red** — a test that a configured run given a mount at the image's
      ledger location leaves a readable ledger on that mount after the container
      is gone. It fails while the image still uses the working-directory default
- [x] 5.2 **Green** — set `ALERT_TRIAGE_LEDGER_PATH` as `ENV` to an absolute
      path under `/var/lib/alert-triage/`, create the directory, and `chown` it
      to the run's user. Declare no `VOLUME` — `design.md` says why
- [x] 5.3 **Red/Green** — a test that a second container over the same mount
      keeps an incident already recorded there, rather than opening an empty
      ledger over it. Seed the ledger through the project's own adapter so the
      test asserts continuity rather than reimplementing the schema
- [x] 5.4 Confirm the mount is writable by the image's user under both a named
      volume and a bind mount, and record which needs host-side ownership work

## 6. The local repeat run

- [x] 6.1 Add `compose.yaml`: the image, a named volume at the ledger location,
      `env_file: .env`, and nothing else it does not need
- [x] 6.2 **Red/Green** — a test that two `docker compose run --rm` invocations
      share one ledger, so the documented local path proves the thing it exists
      for
- [x] 6.3 Confirm no `[project.scripts]` entry was added for this — the decision
      and its reasoning are in `design.md`, and the entry point list stays the
      application's

## 7. The gate builds it

- [x] 7.1 Add an image build step to `.github/workflows/ci.yml`, before the test
      step, tagging what the tests expect
- [ ] 7.2 Confirm the container tests actually run in CI rather than skipping —
      a gate whose new tests all skip has added nothing
- [ ] 7.3 Show the gate red: push a deliberately broken Dockerfile alone to a
      scratch branch, confirm the run fails naming the build step, then remove
      only that defect and confirm green. Record it under
      [Confirmed failure modes](../../../docs/spec-process-cicd-ci.md#confirmed-failure-modes)
      the way slice 13's runs are, and delete the branch

## 8. Documentation

- [x] 8.1 Add the container path to the README's "Running it": the `docker run`
      invocation with its mount, the `docker compose run` repeat, every setting
      a packaged run needs, and plainly what is lost without a mount
- [x] 8.2 Update the README's Setup so a reader with a container runtime and no
      checkout has a path, without displacing the checkout path
- [x] 8.3 Note in `docs/configuration.md` that `ALERT_TRIAGE_LEDGER_PATH` has an
      image default distinct from the working-directory default, if that file
      states the default
- [x] 8.4 Check whether `AGENTS.md` needs anything — it holds practices, and a
      new file kind that must not enter the image is arguably one

## 9. Before calling it done

- [x] 9.1 `uv run ruff check src tests`, `uv run ruff format --check src tests`,
      `uv run mypy`, `uv run pytest` — all four green
- [x] 9.2 Run the suite with `-rs` and confirm the container tests ran rather
      than skipped on a machine that has Docker
- [ ] 9.3 Build the image and perform one real run against a real account with a
      mounted volume, then a second run, and confirm the second was suppressed
      by the cooldown the first one set. This is the green path the smoke tests
      deliberately do not cover, and it is credential-gated in the sense of
      `docs/live-testing.md` — say plainly if it was not run
- [ ] 9.4 `openspec validate containerize-the-run --strict`
