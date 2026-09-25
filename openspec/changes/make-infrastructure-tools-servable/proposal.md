## Why

The infrastructure specialist never reaches the model. Every consultation of it
fails at the first turn with `400 INVALID_ARGUMENT … the specified schema
produces a constraint that has too much branching for serving`, which the model
platform raises before running anything: the Kubernetes tools' own JSON schemas
are too branched for it to serve. The specialist is offered by every deployment
that configures Datadog, is asked for by the manager, and returns nothing every
time.

So the signal the project wrote a whole requirement for — what the service runs
on, what was saturated, what restarted — is absent from every report, and
absent in the shape of a tripped investigation rather than in the shape of an
empty answer. Its live check fails the same way, which is how it was found; it
has been failing since the tools were declared.

## What Changes

- **A specialist's tools are ones the model platform will serve.** A toolset
  whose schemas the platform refuses is reduced to what it will accept, so the
  specialist runs with the tools that work rather than not running at all.
- **The refusal is caught where it can be decided about.** A platform refusing
  a schema is a fact about the deployment, like a toolset it has not
  configured; the specialist reports what it could reach rather than failing
  the investigation.
- **Every specialist is checked against the real model platform.** The check
  that would have caught this is extended so that a specialist which cannot be
  served fails loudly, named, rather than silently returning nothing.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `investigation`: a specialist declares tools the model platform can be
  offered, and a platform refusing one is an absent signal rather than a failed
  investigation.

## Impact

- `investigation/adapters/crew/specialists/infrastructure.py` — the Kubernetes
  tools it declares.
- `investigation/adapters/datadog/tools.py` — how a tool's schema is described.
- `investigation/adapters/adk/` — where a toolset becomes tools offered to the
  model.
- `tests/integration/investigation/adapters/` — the live checks that reach the
  real model platform.

Out of scope: what the infrastructure specialist reports once it runs, which is
already specified. Addressing its metric retrievals, which is
`address-metrics-by-what-they-describe`.
