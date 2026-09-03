# The distributable run: one complete triage pass, started unargued, on any
# machine with a container runtime. See openspec/changes/containerize-the-run/
# design.md for why this is two stages, why the entrypoint is the console
# script, and why no VOLUME is declared.

FROM python:3.13-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv

# Bytecode is compiled once here rather than on every cold start; copied links
# survive the stage boundary where hardlinks would not; and the interpreter is
# the base image's, never one uv fetches behind the build's back.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# The dependency layer is keyed on the lockfile alone, so editing source does
# not reinstall the tree. README and LICENSE come too because the build backend
# reads both out of pyproject.toml.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-dev --no-install-project --no-editable

# --locked, not --frozen, is what makes the lockfile authoritative: --frozen
# only declines to update it, and would happily install from a lockfile that no
# longer agrees with pyproject.toml. --locked fails the build instead.
COPY src/ src/
RUN uv sync --locked --no-dev --no-editable


FROM python:3.13-slim AS runtime

# Only the virtualenv crosses over, so uv, the build cache and the dev group
# stay behind. --no-editable put the package inside it, so src/ is not needed.
COPY --from=build /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

# The ledger's default is relative to the working directory, which inside a
# container means the history dies with the run — dedup, continuation and the
# re-notify cooldown all stop working while the run still exits 0. An absolute
# path states where a durable mount belongs. Only the directory differs from
# the default: the filename stays alert_triage.db so that mounting a checkout's
# own data/ here continues that checkout's history rather than starting a
# second one beside it.
ENV ALERT_TRIAGE_LEDGER_PATH=/var/lib/alert-triage/alert_triage.db

# Deliberately no VOLUME. Declaring one makes the runtime invent an anonymous
# volume per run, so an operator who mounted nothing gets a ledger that appears
# to work, persists where they will never find it, and is empty again next run.
# Without it, no mount means the history is plainly gone — a visible failure
# rather than a hidden one.

# A fixed UID rather than whatever the base image hands out: a named volume is
# initialised with the image's ownership, so the run writes its ledger with no
# host-side permission work. A bind mount to a host directory is the case that
# still needs the host to own it as this user.
RUN groupadd --system --gid 10001 triage \
    && useradd --system --uid 10001 --gid 10001 --no-create-home triage \
    && install --directory --owner triage --group triage /var/lib/alert-triage

WORKDIR /app
USER triage

ENTRYPOINT ["alert-triage"]
