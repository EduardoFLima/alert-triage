## Context

`AdkInvestigator` walks `CREW` and concatenates what each specialist reported.
Two boundaries hold and must keep holding: every tool result crosses `Retrieved`
before a model sees it, and every finding is built only from citations that
resolve. This change puts a manager above the walk and a writer below the
conclusion, without either standing between a result and the check on it. See
proposal.md for motivation, `docs/vision.md` for the crew's shape, and the delta
specs for what is owed.

Two things the crew has never done now run: an agent whose tools are other
agents, and a report body that no longer comes from `triage/domain/report.py`.

## Goals / Non-Goals

**Goals:**

- Routing that is observable — offered and consulted are both readable from
  outside — because slice 10 grades exactly that and cannot grade a decision it
  cannot see.
- A conclusion that cannot outlive its evidence, by the same mechanism that
  already stops a finding outliving its citations.
- A report that survives the writing agent failing.

**Non-Goals:**

- Any change to `Retrieved`, `findings_from`, the evidence callbacks, or a
  specialist declaration. If routing needs a specialist edited, specialists were
  not the declarations slice 7 claimed.
- Tuning any instruction. Slice 10.

## Decisions

**Specialists become tools of the manager rather than steps of a loop.** ADK's
`AgentTool` wraps each specialist's `LlmAgent`, and the Diagnostician is an
`LlmAgent` whose `tools` are those wrappers. The alternative, ADK's transfer/
sub-agent handoff, hands control to the specialist and takes from the manager
the thread it is reasoning on — which is the whole job. `docs/vision.md` already
settles this; the consequence worth naming is that the manager's depth is one,
so `max_agent_hops` bounds nothing here.

**Findings are collected in the manager's `after_tool_callback`, not read back
out of its answer.** That callback sees each `AgentTool` result — the
specialist's structured report — before the manager does. It runs
`findings_from(payload, retrieved, signal)` there, accumulates what survives,
and hands the result on unchanged. Asking the manager to restate its
specialists' findings would put a model between a checked finding and the
report, which is the fabrication path slice 7 closed. The specialists' own
`after_tool_callback` seat stays theirs: they have MCP tools, the manager has
none, so the two callbacks never contend.

**A `Consulted` collector beside `Retrieved`, one per investigation.** It holds
which specialists were offered, which were consulted in order, the findings that
survived, and the consultations it refused. `Retrieved` is evidence and stays
untouched; consultation is a different fact with a different lifetime, and
crowding it into the evidence store would make the class that guards
fabrication also the class that counts model calls. `Findings.consulted` is
derived from it, so a report's claimed scope is a record of what ran rather than
a tuple the composition root passes in — which is what retires `SIGNALS_EXAMINED`
and the `examined=` argument on `build_report`.

**The budget lives in the manager's `before_tool_callback`, refusing rather
than counting.** Same seat, same reason, as the per-agent bound slice 12 will
put there: a callback can decline the call, whereas a coordinator counting
afterwards has already paid for it. The refusal text is shaped like
`RETRIEVAL_FAILED` — explicit that the consultation did not happen — because a
terse error is exactly what a model reads as "that specialist found nothing".

**The budget counts consultations, not specialists, and is stated in code at 8.**
Bounding each specialist to one consultation would forbid the manager's best
move: reading an answer and going back for the detail it now knows to ask for.
So the bound is on hops in total, and 8 is what `docs/vision.md` already
documents for `max_tool_calls_per_agent` applied to a manager — four specialists
reachable with four questions left over. It is stated in code and read from
configuration in slice 12, exactly as slice 7 handled the MCP timeouts: stating
a bound is this slice's, tuning it is not. Deriving it from `len(crew)` was the
first draft and is wrong for the same reason: a crew-sized budget is a
once-each rule wearing a number.

**The contract publishes a `Diagnosis`; the port returns one.** `Findings` gains
`consulted`, and a new frozen value carries the headline, the account, the
hypothesis, the confidence, and the findings. The alternative — a second port
for the conclusion — would let a caller obtain findings without the conclusion
drawn from them and would make "which specialists were consulted" a fact two
components had to agree about. Confidence is a `StrEnum` of declared levels;
anything else the model says resolves to nothing reported, for the same reason
an unresolvable citation drops a finding.

**The account is prose plus a deterministic evidence block, not prose alone.**
The Report agent writes the headline and the narrative; the evidence beneath
each finding is rendered from the checked `EvidenceItem`s by the same code that
renders it today, moved into investigation. Letting the writer reproduce
evidence would reintroduce fabrication at the last hop, where nothing checks it.
This is what lets triage stop reading `Finding`, `EvidenceItem` and `Signal`:
`triage/domain/report.py` keeps the subject, the alert list, and the last-resort
report, and otherwise carries an account it does not compose.

**The Report agent's failure falls back to the deterministic renderer.** The
fallback is the account this project already knows how to build, so it is not
new code kept warm for an emergency — it is the same renderer with no narrative
above it. A report is worth more than its wording, and everything it carries was
gathered before any of it was worded.

**The Diagnostician and the Report agent are `Reasoner` declarations, not
`Specialist`s.** A `Specialist` is rejected without toolsets, and rightly:
what an APM agent *is* includes what it may ask. A reasoner's identity is its
instruction and its output schema. Relaxing `Specialist` to admit a toolless
agent would erase the one invariant that makes a specialist declaration
trustworthy.

**The routing seam is an injected `RunDiagnostician`, mirroring
`RunSpecialist`.** It takes the crew, the investigation's `Consulted` and
`Retrieved`, and the target prompt. In production it builds the manager over
`AgentTool`s; in a unit test it is a stub that consults whichever specialists
the test names, which is how "what was it offered, what did it call" is asserted
with no model and no network. `RunSpecialist` survives unchanged underneath it,
so everything slice 7 and slice 8 established stays exercised.

**Consulting nobody is a completed investigation, not a failure.** It returns no
findings, no consulted signals, and no hypothesis, and the report says no signal
was examined — wording `triage/domain/report.py` already has for a deployment
with no specialists. Failing instead would cost the team its alerts over a
manager's choice, and the run's retry arc is for a platform that could not be
reached, not for a model that decided not to ask.

## Risks / Trade-offs

- **An agent-as-tool result may not arrive as the structured payload the
  specialist declared.** ADK renders a sub-agent's answer for its caller, and
  what the callback is handed may be text rather than the schema. → The
  collector parses defensively, exactly as `_payload` already does for a final
  event, and a payload it cannot read is a specialist that contributed no
  findings rather than a crashed investigation. This is the first thing the live
  run must confirm, and it is this change's gate: if the structured report does
  not survive the hop, findings must be collected from the specialist's own
  `after_agent_callback` instead, which is a seat change and not a design
  change.
- **The manager can consult specialists in parallel if ADK issues concurrent
  tool calls.** `Retrieved` numbers retrievals sequentially and is shared. →
  The budget and the instruction both push toward one consultation at a time,
  and slice 8 already carries this as a known constraint. If the live run shows
  concurrent calls, the fix is to serialise in the callback, not to make the
  evidence store thread-safe for a manager that should not be racing anyway.
- **Cost is now the manager's decision, and a budget of 8 over a crew of four
  bounds the worst case at twice today's specialist calls, plus two reasoning
  calls.** → Permitting the second question is what buys that headroom, and a
  manager spending all of it on every incident would cost more than the fixed
  walk it replaced. The saving is real only if the routing is any good, which is
  unmeasurable until slice 10; task 8.4 is what turns the worst case into a
  measured one. Stated rather than claimed.
- **Two more model calls per incident, both without tools.** → They replace
  formatting work that cost nothing, and buy the two things a reader actually
  wanted. Cheap relative to a specialist, which pays for tool calls as well.
- **A hypothesis is the most quotable thing this system will produce, and it is
  the least checkable.** → The evidence travels with it and the confidence level
  is stated rather than implied; beyond that this is a judgement slice 10 grades
  and no test can settle.
- **`triage/domain/report.py` shrinks and its tests move with it.** → A
  mechanical move, but the one place a silent regression could hide is the link
  rendering, which has its own requirement and its own scenarios. Those tests
  move verbatim rather than being rewritten.

## Migration Plan

The `triage-run` delta modifies **A report says which signals were examined**,
which is a requirement of the unarchived `add-remaining-specialists` change
rather than of `openspec/specs/triage-run/spec.md`. That change is implemented
and merged; archive it before archiving this one, or the modification has
nothing to apply to.

## Open Questions

- Whether the Diagnostician and the Report agent should be nameable under
  `investigation.specialists` for a model of their own. Deferred with slice 8's
  reasoning: an operator can already move every agent with `investigation.model`,
  and slice 10 answers "does the manager want a stronger model" with numbers.
  Until then `crew_for` refuses `diagnostician` by name, which is accurate but
  will read as a bug to the first operator who tries it.
- Whether 8 is the right budget, and whether the same key can serve both a
  specialist's searches and a manager's consultations — `docs/vision.md` leaves
  the second open on purpose. Both want the harness's numbers rather than a
  guess, so both are slice 10's to answer and slice 12's to wire.
- Whether re-asking a specialist is worth its calls in practice. It is permitted
  and bounded; whether managers actually use it well is routing quality, which
  is slice 10's.
