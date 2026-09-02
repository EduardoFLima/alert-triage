## Context

See proposal.md — Why, and slice 10 of `docs/vision.md`. Three things stand in
the way of one specialist reaching two providers, and only the first is
cosmetic: declarations are filed under `adapters/datadog/specialists/`;
`Toolset` names a group without saying whose server groups it; and `Deployment`
carries one `endpoint` and one `headers`, which `connection_for` composes into
every toolset's URL. The reasoners, belonging to no platform, ended up under
`adapters/adk/reasoners/` for want of anywhere better.

## Goals / Non-Goals

**Goals:** the tree stops encoding "one specialist, one platform"; a
declaration can name a different provider per toolset; a deployment supplies
each provider independently; every existing test passes with its imports and
its `Deployment` construction updated and nothing else.

**Non-Goals:** adding the GitHub provider, or any second provider at all — the
capability is proven with a fake. Timeouts from config (slice 12), the README
diagram (slice 15), and anything about what a specialist looks for.

## Decisions

**A provider is a string identifier, defined by that provider's own module.**
`Toolset` gains `provider: str`, and `datadog/mcp.py` exports the constant
Datadog's declarations import. The alternative was an enum in the domain, which
would put every provider's name in one closed list the domain owns — exactly
the coupling a contributor adding a provider should not have to edit. A
constant beside the plumbing that resolves it keeps typos out without making
the domain the registry.

**`Deployment` maps provider → access, and refuses on a provider it does not
hold.** `PlatformAccess` is the endpoint-and-headers pair `Deployment` carries
today; `Deployment.platforms: Mapping[str, PlatformAccess]` replaces the two
fields, and `connection_for(toolset, deployment)` looks up
`toolset.provider`. The alternative — one `Deployment` per provider, threaded
to whichever specialists use it — pushes the lookup into every call site and
makes a two-provider specialist the awkward case rather than the ordinary one.

**Crew selection falls out of what the deployment configured.** `crew_for`
already refuses a configured name nobody declared; it also filters to the
specialists whose every toolset names a provider in `deployment.platforms`, and
refuses if that leaves the crew empty. The alternative is a new
`investigation.crew` allowlist in `config.yaml`; it was rejected as a key that
answers a question credentials already answer, and it can still be added later
for the deployment holding two providers that wants one specialist per signal.
This does mean `crew_for` needs the deployment, which composition.py already
builds first.

**`git mv`, one behaviour-preserving commit, tests moved to mirror.** Layout:
`adapters/crew/specialists/` (the four declarations), `adapters/crew/reasoners/`
(diagnostician, report), `adapters/crew/roster.py` (today's `adk/crew.py` —
which specialists exist is not a framework fact). `adk/` keeps `agent.py`,
`investigator.py`, `consultation.py`, `evidence.py`, `reasoning.py`,
`credentials.py`, `model.py`, `normalisation.py`. `datadog/` keeps `mcp.py` and
`links.py` and gains `dialect.py` and `preview.py` from the old
`specialists/` — both are the platform's grammar and its account's toolset
availability, not declarations. Doing the move in its own commit, before the
`Toolset`/`Deployment` change, keeps the diff that changes nothing separate
from the diff that changes something.

**No new import-linter contract.** `crew/` is another subpackage of an existing
adapters layer, and a declaration importing `datadog/mcp.py` for a provider
name is an adapter reaching an adapter within one context — already permitted,
and correct: the provider's plumbing is where its identity belongs. Adding a
contract that has never been shown to fail would be adding one this repo's own
rule says not to trust.

## Risks / Trade-offs

- **A pure move is where a silent behaviour change hides.** → It goes in its
  own commit with no edits beyond import paths, and the full suite runs on that
  commit before anything else is touched. Live tests are credential-gated and
  will be stated plainly as run or not run.
- **`crew_for` taking a `Deployment` couples roster selection to a framework
  adapter's type.** → `PlatformAccess` and the provider map are plain data;
  `crew_for` reads only the map's keys, so a set of provider names is passed
  rather than the deployment itself.
- **Silent filtering could hide a misconfiguration**: a typo'd provider name
  makes a specialist quietly disappear rather than fail. → The empty-crew
  refusal catches the total case; the partial case is why the refusal names the
  providers a declaration asked for against the ones the deployment holds.
- **The two-provider path has no real second provider to prove it.** → One
  declaration against two fake MCP servers, which is what the spec's scenario
  asks for. It stays unproven against a real second vendor until GitHub lands.
