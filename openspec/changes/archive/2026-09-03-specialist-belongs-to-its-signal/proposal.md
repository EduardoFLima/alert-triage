## Why

Slice 10 of [`docs/vision.md`](../../../docs/vision.md). A specialist is filed
under the one vendor it happens to query today, and — more than a filing
problem — it *cannot* query a second one: `Deployment` carries a single
endpoint with one set of headers, and a `Toolset` names a group on *that*
server. The GitHub deploy-history correlation on the roadmap lands on the APM
specialist, which is where that stops working. Ordered now, immediately after
the crew it reorganises and before the circuit breakers, deployment packaging
and the diagram rework each move the same code a second time.

## What Changes

- `investigation/adapters/adk/reasoners/` and
  `investigation/adapters/datadog/specialists/` become
  `investigation/adapters/crew/reasoners/` and
  `investigation/adapters/crew/specialists/` — siblings, as they are. `adk/`
  is left the framework machinery that runs a declaration; `datadog/` the
  plumbing that says where its server is and how its items are addressed.
  Behaviour-preserving: the existing suite is the safety net.
- `Toolset` gains the provider serving it. A declaration's toolsets may name
  different providers, so one specialist reaches two.
- `Deployment` trades its single `endpoint`/`headers` for a map from provider
  to where that provider is and what authenticates against it. **BREAKING**
  for the composition root and every test that builds a `Deployment`.
- A specialist is offered only where the deployment configures every provider
  its toolsets name — see the assumption below.
- `AGENTS.md`, [`docs/adapters.md`](../../../docs/adapters.md) and the
  `investigation` spec stop saying a specialist lives under the platform it
  queries.

**Assumption, stated because the slice requires an answer and this is ours to
overturn.** The vision leaves open what happens once a Datadog logs specialist
and a Grafana one can sit side by side and the same signal is offered twice.
The answer taken here: a deployment runs the specialists whose providers it has
configured, so a deployment holding only Datadog credentials never offers the
Grafana one and nothing is consulted twice. It needs no new config key and
falls out of the provider map this slice already builds. An explicit
per-deployment allowlist stays available later, for the deployment that
configures two providers and still wants one specialist per signal.

## Capabilities

### New Capabilities

None. Nothing here is a capability the system did not have; what changes is
what a declaration may reach and where it lives.

### Modified Capabilities

- `investigation`: a specialist's toolsets each name a provider and a
  declaration may reach more than one, while staying platform-*specific* in its
  tool names and query dialect; a deployment supplies per-provider endpoints and
  credentials, and offers only the specialists whose providers it configured.
- `project-conventions`: the extension guide describes a declaration that names
  the provider behind each toolset and belongs with the crew rather than under a
  platform directory.

## Impact

- **Moved**: `investigation/adapters/{adk/reasoners,datadog/specialists}` →
  `investigation/adapters/crew/{reasoners,specialists}`, their tests moved to
  mirror, and `investigation/adapters/adk/crew.py`'s imports.
- **Changed**: `investigation/domain/specialist.py` (`Toolset`),
  `investigation/adapters/adk/agent.py` (`Deployment`, `connection_for`),
  `investigation/adapters/datadog/mcp.py`, `app/composition.py`.
- **Unchanged**: every specialist's instruction, schema, signal and tool names;
  the contract; the ports; the layers. No new runtime dependency, so
  `.importlinter`'s vendor list is untouched.
- **Docs**: `AGENTS.md`, `docs/adapters.md`, `README.md` where it names the
  tree. The README diagram is slice 15's and is not redrawn here.
- **Out of scope**: the GitHub provider itself, reading timeouts from config
  (slice 12), and any change to what a specialist looks for.
