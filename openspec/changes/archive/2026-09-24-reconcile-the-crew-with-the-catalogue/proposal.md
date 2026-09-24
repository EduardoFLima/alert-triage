## Why

Datadog has deprecated `search_datadog_service_dependencies` in favour of
`search_datadog_entities`. The APM specialist declares it and its instruction
names it, so a declaration this project ships points at a tool the platform has
said it will stop serving. When it goes, the call comes back refused and the
whole investigation is marked incomplete — the failure mode
`adapters/datadog/preview.py` already describes for a Preview tool an account
cannot reach, arriving this time by deprecation rather than by access.

Two other declarations have drifted from the same catalogue in the same
direction, and are worth correcting while the crew is open and a live run is
being paid for:

- The infrastructure specialist holds the `kubernetes` toolset and cannot ask
  for a rollout analysis, which is how that platform answers "did this start
  after a deploy" in a deployment's own terms.
- The trace specialist writes span queries out of facets it guessed. The two
  metric specialists are taught not to — an empty answer means "not reported",
  not "healthy" — and the trace specialist is the one where a plausible
  invention is hardest to catch.

## What Changes

- **The APM specialist reaches `search_datadog_entities`.** The constant is
  renamed for what the tool is rather than what the old one did, and the line
  describing it is rewritten: the replacement is a catalogue *search*, so the
  model composes an ask where it used to name a subject. The one-hop rule is
  unchanged and matters more, because a catalogue search invites wandering
  that a dependency lookup did not.
- **The infrastructure specialist reaches `analyse_datadog_k8s_rollout`**, with
  the ordering that makes it usable: workloads are found first, and the rollout
  is analysed for one the search named.
- **The trace specialist is taught not to guess a facet.** An instruction
  paragraph in the register the metric specialists already use, plus
  `apm_discover_span_tags` in the Preview branch, so the pair stays honest when
  `APM_TOOLSET_AVAILABLE` flips.
- **`docs/vision.md` stops naming the deprecated tool** in the two places it
  does.
- **The live run confirms all of it.** The existing credential-gated test is
  parameterised per specialist per toolset, so it already covers these once the
  declarations change; what it cannot cover is the Preview branch, which stays
  unverified until the switch flips.

## Capabilities

### New Capabilities

None. Three specialists already have requirements; each gains or corrects one
thing it is asked to establish.

### Modified Capabilities

- `investigation`: the APM specialist's requirement says it reports single-hop
  dependency evidence "where the platform can say", which stays true but is
  satisfied today by a tool being retired. It gains nothing about the tool —
  requirements do not name tools — and its scenario for a neighbour gains the
  constraint that discovering the neighbour is itself a retrieval rather than
  something the specialist knows.
- `investigation`: the infrastructure specialist's requirement asks for the
  workload's state "including restarts and scheduling failures". It gains that
  where the platform can account for a workload's most recent rollout, that
  account is reported with the same standing as the restarts beside it.
- `investigation`: the trace specialist's requirement forbids reporting a
  request it did not retrieve. It gains the other half of that discipline —
  that retrieving nothing is not evidence of nothing, because a query naming a
  facet the service does not carry returns empty for a reason that is about the
  query.

## Impact

- Changed: `investigation/adapters/crew/specialists/apm.py`,
  `infrastructure.py`, `trace.py`, their three unit test files, and the two
  prose mentions in `docs/vision.md`.
- No new dependency, no new configuration key, no contract change, no change to
  what the `Investigator` port takes or returns, and no change to the machinery
  that runs a declaration. Every edit is a tuple, an instruction, and the
  assertion that keeps the two agreeing.
- `.importlinter` is untouched: no new runtime dependency and no new context.

## Out of Scope

- **Where a retrieval's evidence link points.** Three of four specialists get a
  Log Explorer address for evidence that did not come from the Log Explorer,
  and swapping a tool here does not improve or worsen it. Its own change.
- **Error Tracking and Database Monitoring.** Both are real gaps and both are
  now recorded under *Ideas for improvement* in `docs/vision.md`. Neither is a
  correction to a declaration that has drifted, which is what this change is.
- **Flipping `APM_TOOLSET_AVAILABLE`.** That is an account's access changing,
  not a declaration drifting, and `docs/vision.md` already owns it under *A
  Datadog integration that holds up*.
- **`search_datadog_monitors`, profiling, and Datadog's own Bits AI
  investigations.** Considered and deliberately not taken.
- **Unwrapping the MCP result envelope**, which is why per-item citations never
  resolve live. Named in the roadmap already, and a precondition for judging
  what grain a catalogue answer should be cited at rather than part of this.
