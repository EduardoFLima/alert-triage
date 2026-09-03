## Why

A run today is inseparable from the machine it was developed on: it needs uv, a
synced lockfile, a Python the checkout chose, and a working directory the ledger
default is relative to. Nothing anywhere states what a run actually needs in
order to happen somewhere else, so "run this for another team" means reproducing
a developer's laptop. An image is the artefact that answers it — the same run,
started the same way, on any machine that has a container runtime.

Slice 14 in `docs/vision.md`, **rescoped**: containerize only. The Cloud Run and
GKE manifests are dropped from the slice and from the vision's Deployment
section. `docker run` is the deployment story this change delivers; a hosted
target is a later decision that this image is the prerequisite for, not a part
of.

## What Changes

- **An image that performs one run.** Built from the lockfile so the versions it
  carries are the versions CI verified, running as a non-root user, with the
  console script as its entrypoint. Its argument-free invocation is a complete
  run, so a scheduler needs to know nothing but the image name.
- **The ledger's durability becomes an explicit property of a packaged run.**
  A container's filesystem does not survive it, so the default
  `ALERT_TRIAGE_LEDGER_PATH` under the working directory means every run opens
  every incident afresh — dedup, continuation, and the re-notify cooldown all
  silently stop working while the run still exits `0`. The image therefore
  declares where the ledger belongs, and the documented invocation mounts a
  volume there. This is the one thing containerizing breaks that a build alone
  would never reveal.
- **A `compose.yaml` for the local repeat run.** The volume, the `.env`, and the
  image named once, so a second run reaches the first run's ledger without an
  operator re-typing a mount. Deliberately *not* a `[project.scripts]` entry:
  see `design.md`.
- **A build-and-smoke gate.** Integration tests against a built image: that it
  refuses to start and names the missing setting, that a fully configured run
  gets all the way through building its adapters and creating its ledger on the
  mount before failing on the platform it cannot reach, and that a second
  container over the same mount keeps what the first one left. They need no
  credentials and skip — saying why — without a container runtime, the way the
  credential-gated tests skip without credentials. What they deliberately do
  *not* do is exercise a green-path run against a fake platform: the Datadog URL
  this project composes is https-only, so a fake needs a TLS sidecar and a CA
  trusted inside the image, to re-prove run logic that the in-process end-to-end
  test already covers. `design.md` records that trade.
- **CI builds the image on every change**, so the Dockerfile cannot rot behind a
  green suite.
- **Documentation follows the rescope.** `docs/vision.md` slice 14 and its
  Deployment section lose Cloud Run/GKE; the README gains the container path
  beside the checkout path.
- No change to the run's behavior, its exit codes, its configuration keys, or
  any port. The image is a second way to reach the same entrypoint.

## Capabilities

### New Capabilities

- `deployment-packaging`: what the distributable image is and guarantees — that
  it performs one complete run unargued, that it carries the verified
  dependency set, that it runs unprivileged, that the state a run must keep is
  addressable from outside the container and survives it, and that the image is
  built and exercised by the same gate every other check runs in.

### Modified Capabilities

- `project-conventions`: "Quality gate runs on every change" gains the image
  build — a Dockerfile that no longer builds SHALL fail the gate, which today it
  cannot because nothing builds it. "Contributors can set up and verify the
  project from the README" gains the container as a second documented path to a
  working run, with its own verification.

## Impact

- New: `Dockerfile`, `.dockerignore`, `compose.yaml`, and container smoke tests
  under `tests/integration/`.
- Changed: `.github/workflows/ci.yml` (a build step), `README.md` (running it in
  a container), `docs/vision.md` (slice 14 and Deployment rescoped, and slice
  15's forward reference to what slice 14 introduces).
- No new runtime dependency, no new configuration key, no source change expected
  under `src/` — if one proves necessary the change is larger than packaging and
  should be said out loud rather than absorbed.
- `data/` is already gitignored; the mount point the image declares must not
  reintroduce run state into the build context.

## Out of Scope

- **Cloud Run and GKE manifests, Cloud Scheduler, Secret Manager.** Removed from
  the slice at the request that shaped this change. The image is what a hosted
  target would need; choosing one is a later slice.
- **Publishing the image anywhere.** No registry, no tagging scheme, no release
  workflow. The gate builds it; nothing pushes it.
- **A managed ledger store.** Replacing SQLite with Firestore or Cloud SQL is a
  new adapter and a slice of its own. A mounted volume is what a single-writer
  batch job actually needs.
- **Multi-architecture builds.** One architecture, whatever the gate runs on.
- **Slices 10, 11 and 12.** The crew reorganisation, escalation, and the
  configurable circuit breakers land independently; none of them changes what an
  image is, and this change adds nothing they would have to move.
