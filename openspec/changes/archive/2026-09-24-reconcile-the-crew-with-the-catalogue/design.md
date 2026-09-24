## Context

See proposal.md for why. One constraint shapes all of it: a declaration and its
instruction are one thing said twice, and the cheapest way for them to disagree
is to edit one. `tests/unit/investigation/adapters/crew/` asserts both
directions for every specialist, and every decision below keeps that pair
intact rather than widening one half.

## Goals / Non-Goals

**Goals:**

- No declaration naming a tool Datadog has said it will stop serving.
- Each of the three edits confirmed by the live test that already exists,
  without that test being changed.

**Non-Goals:**

- Any change to `Specialist`, `Toolset`, the contract, or the machinery that
  turns a declaration into an agent. If an edit here needs the framework
  touched, it has been mis-scoped.
- Reaching a toolset no specialist reaches today. Widening the crew's reach is
  a roadmap question; this change corrects what the crew already claims.

## Decisions

**The constant is named for the tool, not for the old tool's job.**
`DEPENDENCIES_TOOL` becomes `CATALOG_TOOL`. `search_datadog_entities` carries
identity and ownership as well as dependencies, and a constant promising only
dependencies would be the same half-truth one rename from now. The alternative
— keeping the name because the specialist only wants dependencies out of it —
files a general tool under one caller's use of it, which is what made the old
name outlive the old tool.

**The instruction changes shape, not just a name.** The deprecated tool took a
service and answered with its neighbours; the replacement is a catalogue search
that must be asked a question. So the line describing it says what to ask for
rather than what it returns, and the one-hop rule stays exactly where it is.
The alternative — swapping the name and leaving the sentence — would leave the
model told it has a lookup and handed a search, which it will use by searching
for the service and reporting whatever the catalogue says about it.

**The "an empty answer is about what you asked" rule moves to `dialect.py`.**
It is stated in the APM and infrastructure instructions already and is about to
be stated in the trace one, and `dialect.py` exists for exactly this: its own
docstring argues that a rule stated twice is a rule that can be corrected once.
The *principle* moves — an empty answer means the thing is not reported, which
is not the same as the thing being healthy — while the mechanics stay local,
because the metric specialists have a listing tool to check against and the
trace specialist has one only under Preview. The alternative, a third wording
in a third file, is the drift this change is correcting arriving by our own
hand.

**The trace specialist gets the discipline whether or not it gets the tool.**
`apm_discover_span_tags` is Preview-only, so with `APM_TOOLSET_AVAILABLE` off
the specialist is told the rule and given no way to check. That is still worth
saying: the rule's weaker form — treat an empty span search as a question about
the query — changes what the specialist reports, and the tool only makes the
check cheap. Declaring it in the Preview branch keeps the pair honest for the
day the switch flips.

**The rollout is analysed for a workload that was searched for.**
`analyse_datadog_k8s_rollout` takes a cluster, a namespace and a deployment
name, none of which the specialist holds until `search_datadog_k8s_resources`
has answered. So the instruction states the order, exactly as the trace
specialist's states "search before you fetch". The alternative, listing the
tool and leaving the ordering to the model, is how a specialist spends a call
asking for a workload it named itself.

## Risks / Trade-offs

- **The deprecated tool may already be gone.** → Then the live test is failing
  against a real account today and nobody knows, because CI skips it. Running
  it is the first task rather than the last, so the change starts by learning
  whether it is a correction or a repair.
- **`analyse_datadog_k8s_rollout` is spelled with an `s`,** while its
  neighbours in the same catalogue are spelled `analyze_datadog_logs` and
  `analyze_datadog_error_tracking_errors`. → A tool name is a string that
  either exists or does not, and the live test is what settles it. Worth
  naming here because it is exactly the kind of thing a careful reader
  "corrects" into a tool that does not exist.
- **The Preview branch cannot be verified.** → It joins the four Preview tools
  already declared and already unverified. `docs/vision.md` owns that gap under
  *A Datadog integration that holds up*; this change does not widen it beyond
  one more name in the same branch.
- **A catalogue search wanders where a lookup could not.** → The one-hop rule
  is already in the instruction and already asserted by a unit test. This adds
  the spec constraint that a neighbour must have been retrieved, which is what
  makes wandering discardable rather than merely discouraged.

## Migration Plan

None. Nothing is stored, nothing is configured, and no declaration is read from
anywhere but code. A deployment picks the change up by running the new version.

## Open Questions

- **What grain a catalogue answer should be cited at.** The APM instruction
  currently offers "a dependency map" as its example of an aggregate cited as
  `call-N`. Whether `search_datadog_entities` returns discrete entities is a
  question about a live payload — and moot until the MCP result envelope is
  unwrapped, since per-item citations do not resolve live at all today. The
  example is reworded to something still true either way rather than guessed
  at.
- **Whether the replacement needs arguments the old tool took.** The Service
  Dependencies API filters by environment and by a primary tag. If the
  catalogue search needs the same narrowing to answer usefully for an account
  with several environments, the instruction owes the model a word about it.
  The live run is what shows this, and it shows it as a vague answer rather
  than as an error.
