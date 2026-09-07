## Context

See [proposal.md](proposal.md) — Why. The state this builds on:

- `CircuitBreakers` has been resolved into `Config` since slice 1 and read by
  nothing. Its five fields carry the documented defaults as plain literals,
  where every other section states them as `ClassVar`s.
- The one bound that exists is `MAX_CONSULTATIONS = 8` in
  `adapters/adk/consultation.py`, enforced by `bound_consultations_callback` on
  the manager's `before_tool_callback` and interpolated into the
  Diagnostician's instruction. After slice 10 that import is the only edge from
  `adapters/crew/` into `adapters/adk/`.
- A specialist's `before_tool_callback` is `log_tool_call`, which slice 7 left
  as a seat: it writes down the call and enforces nothing.
- `CONNECT_TIMEOUT_SECONDS` and `READ_TIMEOUT_SECONDS` are stated in
  `agent.py` at 30.0 each, explicitly pending this slice.
- The refusal machinery already exists and works: a refused consultation is
  recorded on `Consulted`, answered with wording a model cannot read as an
  empty result, and surfaces through `Findings.retrieval_failures` into a report
  marked incomplete. Every bound added here rides that path rather than
  inventing one.
- `Specialist` declares a name, signal, instruction, schema, toolsets and an
  optional model. There is no field for a sub-agent, so no declaration can
  express an agent beneath a specialist.

## Goals / Non-Goals

**Goals:**

- Every key the `circuit_breakers` section resolves is read by what it bounds.
- Each bound is enforced by declining the call, not by counting after it.
- A trip is reported as an account cut short, never as a signal that was clean.
- The number the reasoning is told and the number enforced are one value.

**Non-Goals:**

- Tuning any default against evidence. Every number here is the one
  `docs/vision.md` documents, except the one this change re-bases, and settling
  them is the evaluation harness's job.
- Bounding the depth of agents calling agents. Nothing can express that depth,
  so nothing can violate a rule about it.
- Bounding the report agent's wording run. It reaches no platform, already
  falls back to a composed account when it fails, and losing prose is not the
  runaway a breaker exists to catch.

## Decisions

### Two per-agent keys, one job each

`max_agent_hops` becomes how many specialist consultations one investigation may
make; `max_tool_calls_per_agent` becomes how many tool calls one specialist may
make. A hop is the manager reaching a specialist and that specialist reporting
back, so counting hops is counting consultations.

*Why over the alternatives:*

- **The vision's reading** — `max_tool_calls_per_agent` bounds both the manager
  and the specialists, `max_agent_hops` bounds a handoff depth. It left open
  whether one key can serve two questions and deferred the answer to a harness
  that does not exist. This split answers it structurally instead: the questions
  are different, so the keys are different, and neither waits on evidence.
- **`max_agent_hops` as a traversal depth limit** — the reading the vision
  gestures at, load-bearing when multi-hop dependency traversal lands. Rejected
  as speculative: today the depth is a constant of the code, no declaration can
  vary it, and a bound nothing can violate is a bound nothing has shown to
  enforce anything. Multi-hop traversal is a roadmap item and can name its own
  key, or re-scope this one, when it arrives.
- **Removing `max_agent_hops`** — consistent with removing `max_mcp_retries`,
  but throws away a key that has an obvious job going unfilled.

**Consequence:** the default moves from 2 to 8. A bound of 2 consultations would
forbid the breadth the Diagnostician's instruction explicitly asks for, and
would contradict the standing requirement that the bound exceed the declared
crew. `docs/vision.md`'s breaker table and its two `max_agent_hops` /
`max_tool_calls_per_agent` paragraphs are rewritten to match — the same way
slice 7 rewrote that section when it decided the MCP pair.

### The bound lives in configuration, and both claimants read it

`MAX_CONSULTATIONS` leaves `adapters/adk/consultation.py`. Its value becomes
`CircuitBreakers.DEFAULT_MAX_AGENT_HOPS`, a `ClassVar` beside the field, which is
the convention `Grouping`, `Ingestion`, `ReNotify`, `Ledger` and `Investigation`
already follow. Every breaker default is restated that way, so the section stops
being the one that hides its numbers in literals.

The instruction and the enforcement then read one value that neither owns: the
`CircuitBreakers` handed to the investigator. The vision names this exact
requirement — what the manager is *told* it has and what is *enforced* must
never disagree — and a configurable budget is what makes the disagreement
possible for the first time.

### The Diagnostician's instruction becomes a function of its budget

`DIAGNOSTICIAN_INSTRUCTION` is an f-string interpolating `MAX_CONSULTATIONS` at
import time, and `DIAGNOSTICIAN` is a module constant. Both become functions of
the budget: `diagnostician_instruction(hops)` and `diagnostician(hops)`
returning a `Reasoner`. `build_manager` calls it with the configured value.

This is what drops the `crew → adk` import: the declaration is told its budget
rather than reaching for it. The alternative — ADK instruction templating filling
the number from session state — hides a project decision inside framework
behavior and cannot be unit-tested without the framework.

*Note:* `REPORT_WRITER` and the four specialists stay module constants. Only the
declaration that needs a configured number becomes a function of one.

### `Deployment` carries the breakers

`Deployment` gains a `breakers: CircuitBreakers` field. `connection_for` then
reads `mcp_call_timeout_seconds` for both `timeout` and `sse_read_timeout`,
retiring the two module constants; `build_agent` reads
`max_tool_calls_per_agent`; `build_manager` reads `max_agent_hops`.

*Why over the alternatives:*

- **A new parameter on each builder** — three signatures grow, and the value is
  a deployment fact travelling with the other deployment facts anyway.
- **An adapter-local `Bounds` type translated from `CircuitBreakers`** — a
  translation layer with one implementation on each side. `configuration` is a
  generic subdomain every context may depend on directly, which is exactly what
  spares this one.

One key feeds both the connect and the read timeout. They are two halves of one
bound an operator states once, and splitting them would be a schema change
nothing has asked for.

**What the timeout actually bounds, given the retry we do not own.** ADK's
`retry_on_errors` sits *below* `before_tool_callback`: the callback fires in
`flows/llm_flows/functions.py` and the retry decorates
`MCPTool._run_async_impl`, inside the call the callback has already permitted.
So a transport retry never re-enters the callback, and
`max_tool_calls_per_agent` does not count it — the two bound different layers,
which is why removing `max_mcp_retries` leaves a genuine gap rather than a
covered one.

The gap is bounded by time instead of by count. A retried call is two attempts
of `mcp_call_timeout_seconds`, so the worst case for one tool call is twice the
stated bound, and `max_investigation_duration_seconds` is what bounds the
accumulation of those. Worth stating because an operator reading "thirty
seconds" should know a single call can take sixty.

### A specialist's calls are counted per specialist, per investigation

`log_tool_call` gains a body, becoming the seat slice 7 said it was. The count
is held in a per-investigation record beside `Retrieved` and `Consulted` — one
entry per specialist, cumulative across every consultation of it, because the
agent is built once per investigation and reused. A declined call is answered
with refusal wording in the register `RETRIEVAL_FAILED` and
`CONSULTATION_REFUSED` already use, and recorded so it reaches
`Findings.retrieval_failures`.

*Alternative considered:* resetting the count per consultation. Rejected — a
manager that consults one specialist five times would then get five full
budgets, which is the runaway the bound exists to stop wearing a different shape.

### Duration trips in two stages

- **Stage one, graceful.** The investigation is given a deadline. Both
  `before_tool_callback` seats — the manager's and each specialist's — decline
  once it has passed, so the reasoning stops gathering and concludes on what it
  holds. This is the common case and it keeps the hypothesis.
- **Stage two, backstop.** `asyncio.timeout` around the manager's run inside
  `run_with_adk`. A model that hangs between tool calls never reaches stage one,
  and stage one alone would leave that runaway unbounded.

`Consulted` and `Retrieved` are owned by `AdkInvestigator` and passed into the
run, so cancelling the run destroys neither: everything gathered before the
timeout survives it. That is what makes stage two produce a partial report
rather than nothing.

Stage two is safe from the retry below it: `retry_on_errors` checks
`asyncio.current_task().cancelling()` and re-raises rather than reattempting, so
a cancelled call is not converted into a fresh attempt that outlives the bound
that cancelled it.

The deadline is computed from `time.monotonic`, injected so a test can drive it
without sleeping. Monotonic rather than wall-clock, so a clock adjustment
mid-investigation cannot trip or defer a bound.

### A trip with nothing gathered is a failure

`AdkInvestigator.investigate` already raises `InvestigatorError` when every
retrieval failed, so the incident keeps its attempts rather than being reported
as quiet. A breaker that trips before any finding was produced takes the same
exit, for the same reason.

This is deliberately distinguished from the outcome slice 9 added — *no
specialist consulted at all is an ordinary result* — which covers a manager that
**chose** not to ask. A manager that was **stopped** from asking is a different
fact, and the difference is exactly the one the refusal wording exists to keep.

### The report says which bound was reached, through the channel that exists

A trip's reason is recorded as a refusal string and reaches the report through
`Findings.retrieval_failures`, which already renders as the incompleteness note.
No contract field is added: `Findings` already distinguishes "gathered
incompletely" from "found nothing", and a breaker is one more reason for the
first.

### The `crew → adk` rule is a contract, shown red first

A `forbidden` contract in `.importlinter`, added to the list
`tests/unit/test_architecture.py` asserts is present, so the rule going missing
fails a build. Shown red against a deliberate `crew → adk` import before it is
trusted green, like every other contract in that file.

## Risks / Trade-offs

- **`max_agent_hops` changes meaning under an existing key** → A deployment that
  set it to 4 meaning "depth" now gets 4 consultations. Deliberate rather than
  papered over: v1 runs manually, nothing consumed the key, and a rename would
  cost the vision's own vocabulary for a migration nobody needs. The vision,
  `config.yaml` and the config spec all state the new meaning.
- **Removing `max_mcp_retries` breaks a deployment that sets it** → It is
  refused by name at startup by the existing unknown-key path, which is the
  loudest available failure and the outcome that path was built for. Silent
  removal was the alternative and is the thing that path exists to prevent.
- **A cumulative per-specialist budget can starve a follow-up consultation** →
  A specialist consulted three times shares eight calls across all three. Eight
  against a typical one-to-three calls per consultation leaves room, and the
  harness is what should settle the number. The refusal is legible when it
  happens, rather than silent.
- **Stage two cancels mid-tool-call** → `Retrieved` records a retrieval when it
  completes, so a cancelled call contributes nothing rather than half an item.
  The call is lost, not corrupted.
- **Two stages could double-count one trip** → One reason is recorded per trip
  and the stages are ordered, so an investigation stopped by the backstop after
  stage one already declined calls reports both facts truthfully rather than
  twice.
- **Four sequential specialists press on the duration bound** → Noted since
  slice 8. This slice is what makes the pressure visible instead of unbounded:
  a run that would have taken ten minutes now reports at five, incomplete,
  which is the signal a team wanted.

## Migration Plan

No data migration. One operator-visible step: a deployment setting
`circuit_breakers.max_mcp_retries` must delete the key, and is told so by name
at startup. A deployment setting `max_agent_hops` should re-read what it now
means. Rollback is reverting the change; nothing persists.

## Open Questions

Deferrable without changing the specs, the approach, or the tasks:

- Whether `max_agent_hops` and `max_tool_calls_per_agent` want genuinely
  different values in practice, or converge. The evaluation harness answers it;
  both keys are already separate, so either answer is a default change.
- Whether a specialist's budget should be per-specialist or per-consultation
  once real routing traces exist. Same answer, same harness.
- Whether the duration bound should cover the report agent's wording run. It is
  excluded here for the reason under Non-Goals; a slow wording step would be
  evidence to revisit it.
