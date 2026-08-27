# Testing against a real account

Almost everything is exercised offline, against a fake MCP server and a
scripted model. Seven tests are not, because three things cannot be
established by a fake — a fake is built from the same assumptions the code is:

- that the tool names in a specialist's declaration **exist** on Datadog's MCP
  server, and that the server's filter admits them,
- that a real model given the instruction **actually calls** them,
- that a URL this project composes is a route the platform **accepts**, rather
  than the 404 a route built from the wrong kind of identifier returns.

They are gated on real credentials and skip without them, which is why a fresh
clone and CI stay green.

## Running them

```bash
export DD_API_KEY=... DD_APP_KEY=... GOOGLE_API_KEY=...
uv run pytest tests/integration/investigation/adapters/datadog \
              tests/integration/triage/adapters/datadog -rs
```

Those two paths are exactly the seven; nothing else in the suite is
credential-gated. `-rs` is what tells you they ran rather than skipped past —
without it a skip and a pass look alike in the summary, which is how "7
skipped" scrolls by unnoticed.

A run costs a model call and a handful of platform calls.

## Pointing them at the `.env` you already have

The credentials have to reach the **process environment**: the skip is decided
as the module loads, and nothing in the test path reads `.env` on the way in.
Rather than exporting by hand, let `uv` put the file into the environment for
the run:

```bash
uv run --env-file .env pytest tests/integration/investigation/adapters/datadog \
                              tests/integration/triage/adapters/datadog -rs
```

It parses the file the way the application does and applies it to that one
command only, so nothing leaks into the shell afterwards. Anything already
exported still wins, which matches how a `.env` behaves at runtime.

For a shell that is not going through `uv`, or to keep the values for a whole
session:

```bash
set -a; source .env; set +a     # every assignment exported until the shell exits
```

`source` is the blunter of the two — it is the shell reading the file, not a
dotenv parser, so an unquoted value containing spaces or a `#` mid-line will
not survive it intact. Prefer `--env-file` unless you want the values to
persist.

Loading `.env` is deliberately not automatic. A stray file in a checkout would
otherwise start reaching a real account and spending model calls during an
ordinary `uv run pytest`, and the gate reading the process environment is what
keeps that an explicit act.

## The link checks

Two of the seven follow an address this project built and rule out a 404. They
are worth running alone after touching anything that composes a URL:

```bash
uv run pytest -k opens_rather_than_404s -rs
```

A redirect to a login page counts as an answer — these are UI addresses and
the check holds no session — so what is being ruled out is specifically the
404, not "you are not signed in".

This is the check the project did not have when an alert's link was built as
`/event/event?id=<v2 identifier>`, a route that reads as working until a human
follows it. A unit test can only assert the string it just composed, which is
why these exist.

## What "live" means twice

`-k live` is the wrong selector: it collects fourteen tests, not seven. The
email and Teams channel tests are named `_live` in a different sense — a real
server started **inside the test process**, no account and no credentials —
and those run on every ordinary `uv run pytest`. Select the seven by path, as
above.

## Settings

`ALERT_TRIAGE_LIVE_SERVICE` names a service in the account under test,
defaulting to `checkout`. A quiet service is a valid answer: these confirm the
retrieval happened, not that it found anything.

The credentials themselves are the ordinary connection settings, documented in
[`configuration.md`](configuration.md) — `DD_API_KEY` and `DD_APP_KEY` for the
platform, `GOOGLE_API_KEY` for the model the specialist reasons on, plus
`DD_SITE` and `DD_WEB_SUBDOMAIN` where the account is not on `datadoghq.com`
or is served from a sub-domain of its own.
