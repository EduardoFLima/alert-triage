# Running it in a container

The same run as from a checkout, on any machine with a container runtime and no
Python. The image performs one complete run when started with no arguments, so
whatever starts it needs to know nothing but its name.

The [README](../README.md#in-a-container) carries the short version — the build,
the run, and the one mount you must not forget. This is everything else.

## The full invocation

```bash
docker build -t alert-triage .

docker run --rm \
  --env-file .env \
  -v alert-triage-ledger:/var/lib/alert-triage \
  -v ./config.yaml:/app/config.yaml:ro \
  -v ~/.config/gcloud/application_default_credentials.json:/var/secrets/google/application_default_credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/google/application_default_credentials.json \
  alert-triage
```

Nothing follows the image name, because the image *is* the run. Everything it
needs is handed to it from outside — the image carries no credentials and no
`config.yaml`, so one image serves every deployment.

| Part | What it does | Leaving it out |
| --- | --- | --- |
| `--rm` | Deletes the container once the run exits. A run is one pass, not a service. | Every run leaves a stopped container behind. Nothing is lost: the history is on the volume, not in the container. |
| `--env-file .env` | Connection settings — the Datadog and model credentials, and where reports go. Docker sets them as real process variables before the run starts. | Pass them one at a time instead: `-e SCOPE_OWNER=sre -e DD_API_KEY=... -e DD_APP_KEY=... -e GOOGLE_API_KEY=... -e ALERT_TRIAGE_TEAMS_WEBHOOK_URL=...`. With neither, the run refuses to start rather than fetch alerts it could tell nobody about. |
| `-v alert-triage-ledger:/var/lib/alert-triage` | The incident history, kept where the container cannot take it away. Docker creates the named volume the first time it is used. | The run keeps no history, and still exits `0`. This is the one that bites — see below. |
| `-v ./config.yaml:/app/config.yaml:ro` | Behaviour — what is watched and how it is triaged. `/app` is the image's working directory, which is where the run looks for the file. `:ro` mounts it read-only, because config is input and nothing in the run should be able to write it back. | Every key falls back to its documented default, which is fine as long as `scope` reaches the run some other way — `SCOPE_OWNER`, `SCOPE_SERVICES`, or both. |
| `-v …/application_default_credentials.json` and `-e GOOGLE_APPLICATION_CREDENTIALS` | **Only with `GOOGLE_GENAI_USE_ENTERPRISE=true`**, which reaches the model through the enterprise platform instead of an API key, using what `gcloud auth application-default login` wrote. Set `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` with it — a container has no `gcloud` to discover them from. `:ro` because these are your own credentials: right for your machine, not for a scheduled deployment. | Set `GOOGLE_API_KEY` in `.env` instead — the simpler path, and what the image assumes. Without the enterprise flag the key is required and this mount is ignored. |

## The volume is not optional in practice

A container's filesystem does not survive it, so a run without that mount keeps
no incident history: dedup, continuation, and the two-day re-notify cooldown all
stop working, and every run opens every incident afresh and reports it again —
while still exiting `0`. Nothing warns you. The image keeps the ledger at
`/var/lib/alert-triage/`; mount something durable there.

A named volume is the easy answer, because it is initialised with the image's
own ownership and so asks nothing of the host. Swap it for a bind mount —
`-v ./data:/var/lib/alert-triage` — to carry on from the history a local run
already built: the image keeps the ledger under the same filename a checkout
uses, so the two share one file rather than opening one each. The cost is
ownership. The run is an unprivileged user (UID 10001), and on Linux the host
directory must be owned by it, which `sudo chown -R 10001:10001 data` settles.
Docker Desktop on macOS and Windows ignores ownership, so a bind mount that
works there can still fail on a Linux host.

## For a repeat local run, use `compose.yaml`

It writes the mount and the `.env` down once, so the second run reaches the
first run's ledger without anyone retyping them:

```bash
docker compose run --rm triage
```

It mounts no `config.yaml`, because it cannot do so safely: `env_file` takes
`required: false` and a bind mount has no equivalent, so naming a file that a
fresh clone does not have makes Docker create a *directory* in its place and
mount that over the path the run reads. Put the mount in a
`compose.override.yaml` instead, which compose merges when it is there and
ignores when it is not:

```yaml
services:
  triage:
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ~/.config/gcloud/application_default_credentials.json:/var/secrets/google/application_default_credentials.json:ro
    environment:
      GOOGLE_APPLICATION_CREDENTIALS: /var/secrets/google/application_default_credentials.json
```

The leading `./` is not optional. A source with no `/` in it is read as the name
of a volume rather than as a path, and compose refuses the project with
`service "triage" refers to undefined volume config.yaml`. A `~` is expanded.

That file is gitignored, like `config.yaml` and `.env`, because which settings a
machine runs with is that machine's business. For a one-off, pass the mount on
the command line instead:
`docker compose run --rm -v ./config.yaml:/app/config.yaml:ro triage`.

## Where the settings themselves are documented

Every key, every variable, and every default is in
[`configuration.md`](configuration.md). What reaches the log and how to get the
part held back is in [`logging.md`](logging.md).
