## Context

See `proposal.md` — Why. Three facts about the codebase shape every decision
below. The run is a batch job that exits, not a service. Its only durable state
is one SQLite file whose location comes from `ALERT_TRIAGE_LEDGER_PATH`, opened
and schema-created by `app/composition.py` before any fetch. And the Datadog
alert source composes its URL as `https://api.{DD_SITE}` — the scheme is fixed
in the vendor client's server template, not chosen by this project.

## Goals / Non-Goals

**Goals:** an image that is the same run on any machine with a runtime; a local
invocation that reaches the previous run's ledger without the operator restating
where it is; a gate that fails when the image stops building or stops running.

**Non-Goals:** a registry, a tag scheme, multi-arch builds, or any hosted target
— see `proposal.md` — Out of Scope. Also non-goal: re-proving the run's own
logic through the container. The image is a delivery vehicle; what a run decides
is already specified and tested in-process.

## Decisions

**A multi-stage build on `python:3.13-slim`, with `uv` doing the install.**
The build stage copies the `uv` binary from its published image, runs
`uv sync --locked --no-dev --no-editable` into a self-contained virtualenv, and
the runtime stage copies only that virtualenv and the installed package.
Alternative: a single stage, which is fewer lines. Rejected because the runtime
would then carry `uv`, the build cache, and the dev group, and "no development
tooling in the image" is a requirement rather than a preference. Alternative:
Alpine, for size. Rejected because `datadog-api-client`, `google-adk` and the
MCP SDK ship manylinux wheels and musl forces source builds — a slower, more
fragile build to save tens of megabytes on an image nothing pushes anywhere.
`--locked` is what makes the lockfile authoritative, and the distinction cost a
red test to find: `--frozen` only declines to *update* the lockfile and will
happily install from one that no longer agrees with `pyproject.toml`, which is
exactly the silent drift the lockfile exists to prevent. `--locked` fails the
build instead.

**`ENTRYPOINT` is the console script, exec form.** `ENTRYPOINT ["alert-triage"]`
with no `CMD`, so `docker run <image>` unargued is a complete run and the exit
status is the run's own. Alternative: `CMD ["python", "-m", "alert_triage"]`,
which is the same job. Rejected because a `CMD` is replaced by any argument an
operator passes, so the image would quietly stop being a triage run the first
time someone appended something; and because the console script is what the
README already documents. Exec form rather than shell form so no `sh` sits
between the signal and the process.

**The ledger lives at `/var/lib/alert-triage/`, set as `ENV` in the image, and
the image declares no `VOLUME`.** The `ENV` means the operator does not have to
know the variable to get a working default, and an absolute path under
`/var/lib` cannot be confused with the `data/` directory in the build context.
Alternative: leave the default `data/alert_triage.db` relative to the working
directory and mount over it. Rejected because it makes the mount point depend on
where the image happens to `WORKDIR`. The `VOLUME` omission is the deliberate
half: declaring one makes Docker invent an anonymous volume per run, so an
operator who mounted nothing gets a ledger that *appears* to work, persists
somewhere they will never find, and is empty again next run. Without it, no
mount means the ledger lives in the container layer and is plainly gone — a
failure that is at least visible.

**`compose.yaml`, not a `[project.scripts]` entry.** This was raised as an
option and is worth stating why it loses. A `[project.scripts]` entry point must
name a Python callable, so a `docker run` shortcut means shipping a Python
function whose body shells out to `docker`. That function is installed into the
wheel, which means it is installed *into the image* — a container carrying a
command that starts a container. It also puts a second entry point beside
`alert-triage` in the distribution's public interface, where an operator has to
work out which of the two is the application. And it makes the package depend on
Docker being present with no way to declare it. `compose.yaml` is the tool built
for the actual want — the image, the named volume, and `env_file: .env` written
down once, so `docker compose run --rm triage` is the repeat run and the mount
is not re-typed. It is a repo file, so it never enters the image or the wheel.

**A fixed non-root UID, and a named volume rather than a bind mount in
compose.** The image creates a user with an explicit UID/GID and `chown`s the
ledger directory to it. A named Docker volume is initialised with the image's
ownership, so the run can write it with no host-side permission work; a Linux
bind mount to a host directory would be owned by the host user and the run would
fail to create the database. Bind mounts are documented as the option for an
operator who wants the file where they can see it, with the ownership caveat
stated. Alternative: run as root, which makes every mount work. Rejected — a
job that reads alerts and sends reports needs no privilege, and this is cheap.

**The smoke tests shell out to `docker` from pytest and skip without it.** They
live in `tests/integration/`, locate the image by tag from an environment
variable with a documented default, and are gated on `shutil.which("docker")`
plus a working daemon, skipping with the reason named — the same shape as the
seven credential-gated tests, so a fresh clone stays green. They mirror
`test_installed_distribution.py` deliberately: that file already proves the
console script is wired by running it in a bare environment and asserting it
refuses on `scope.owner`, and the container's first test is exactly that
assertion one layer out.

**The green-path run is not exercised through the container.** A run that exits
`0` must complete a Datadog fetch, and `https://api.{site}` cannot be pointed at
a plain-HTTP stub. Getting there means a TLS sidecar, a generated CA, and
arranging for the vendor client inside the image to trust it — machinery whose
only payoff is re-running logic `tests/integration/app/test_end_to_end.py`
already covers in-process with injected fakes. Instead the fully-configured test
asserts the run reaches the *fetch* and fails there: everything the image is
responsible for — dependencies present, adapters constructible, the ledger
created on the mount, the non-root user able to write it — has happened by that
point, and nothing after it is the image's business. Alternative considered and
deferred: a `compose` profile with a TLS fake platform, if a true green-path
container run is ever wanted.

**CI builds the image in its own step, before the test step.** The gate tags it
with what the tests expect, so `uv run pytest` finds it already built rather
than each test racing to build one. Alternative: let the tests build on demand.
Rejected because a build failure would then surface as a confusing test error
instead of a named build step, and because the build is worth failing on even if
the smoke tests skip.

## Risks / Trade-offs

- **A container with no mount silently keeps no history, and still exits `0`.**
  → The `VOLUME` omission makes the loss total rather than hidden in an
  anonymous volume, the README states it, and the compose file — the documented
  local path — always mounts. Not fully mitigated: a hand-written `docker run`
  without `-v` will still look like it worked. A run that logs its resolved
  ledger path would close this; it is a source change and is left out of a
  packaging slice rather than smuggled in.
- **The gate gets slower by an image build.** → Layer caching keyed on the
  lockfile means the dependency layer is rebuilt only when dependencies change,
  which is rarely.
- **Docker-dependent tests skip silently on a developer machine without it.**
  → `pytest -rs` already reports skips and the README documents it; CI always
  has a runtime, so the tests always run somewhere.
- **The image build is a second place dependencies are installed**, and it can
  drift from `uv sync`. → `--locked` against the same committed lockfile is what
  keeps them the same set, and the build fails rather than drifting.
- **The smoke test asserts a failure message**, so a reworded fetch error breaks
  it. → It asserts the stage the run names, which is structured output the
  existing tests already depend on, not prose.

## Migration Plan

Additive. No existing invocation changes, no configuration key is added or
retired, and nothing under `src/` moves — a checkout run is byte-for-byte the
run it was. Rollback is deleting the new files and the CI step.

## Open Questions

- Which base image tag to pin to, exactly, and whether to pin by digest. Safely
  a later call: it changes no requirement and no task.
- Whether the compose file should also carry a profile for the live
  credential-gated tests. Adjacent, and answerable once the image exists.
