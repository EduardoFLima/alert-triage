## Why

Every investigation runs all four specialists and hands back a flat list of
observations. Nothing decides which signals an incident actually needs, nothing
reasons across what came back, and nothing states what it thinks is going on —
so the human still does the two hardest parts: joining the signals up and
deciding whether to act. Paying four models per incident to produce a list is
also what makes an hourly first-pass triage too expensive to keep running.

Slice 9 in `docs/vision.md`. It follows slice 8 because a manager choosing
between specialists needs specialists to choose between, and it precedes slice
10 because the judgements most worth grading — which specialists an incident
needed, and what was concluded from them — do not exist until it lands.

## What Changes

- **A Diagnostician agent, the crew's manager.** It reaches each specialist as
  a tool, calls the ones this incident needs, reads what came back, and chooses
  the next from it. Specialists stop being a sequence the coordinator walks.
- **An investigation concludes.** It produces a hypothesis with an explicit
  confidence level, drawn from the findings that survived the evidence check.
  A hypothesis left standing on no surviving finding is dropped, not reported:
  the evidence discipline of slice 7 applied one level up.
- **A Report agent writes the account** the team reads — the hypothesis, what
  it rests on, and what is worth checking — kept a separate agent from the
  Diagnostician so reasoning quality and wording are tuned apart. Evidence
  itself is still rendered mechanically from the checked items, never written
  by a model.
- **Findings gain the signals that were consulted.** A specialist nobody called
  is not a specialist that found nothing, and a report that cannot tell the two
  apart is the failure mode slice 7 fixed for a failed search, one level up.
- **A report says what it thinks.** The last-resort report and the alert list
  stay triage's; the account of the investigation arrives already written.
- **Report formatting leaves `triage/domain/report.py`.** Triage stops reading
  `Finding`, `EvidenceItem` and `Signal` to build a body, and the composition
  root stops passing `SIGNALS_EXAMINED` — an investigation now says what it
  consulted rather than being told what the crew declares.
- **A consultation budget, not a circuit breaker.** One investigation may make
  a bounded number of specialist consultations in total — the manager may go
  back to a specialist with a narrower question, and what is bounded is how many
  such questions an incident may cost, not how many a given specialist may take.
  Refused deterministically rather than by the model's goodwill, at the value
  `docs/vision.md` already documents. The configurable bound is slice 12's.
- **BREAKING for the port, not for the run**: `Investigator.investigate`
  returns a diagnosis carrying the findings rather than the findings alone.
  `AlertSource`, `TriageLedger`, `Notifier`, `TriageReport` and every
  configuration key are untouched.

## Capabilities

### New Capabilities

None. Investigation already specifies what an investigation is asked and what
it owes; this changes what it is entitled to say and who decides what it looks
at.

### Modified Capabilities

- `investigation`: adds requirements for a manager that selects specialists per
  incident, for the record of which signals were consulted, for a hypothesis
  with an explicit confidence level grounded in surviving findings, for the
  account a report agent writes and what it may not write, and for the
  consultation budget. Modifies "An investigation returns findings, not a
  conclusion", which this slice is the reversal of, and the requirement that a
  caller cannot observe how many specialists ran — a caller now learns which
  were consulted, and must.
- `triage-run`: modifies "The report a run sends", which forbids a hypothesis
  and a confidence level on the grounds that nothing produces one, and "A
  report says which signals were examined", where what was declared and what
  ran stop being the same tuple.

## Impact

- New: a `Reasoner` declaration and two declarations under
  `investigation/adapters/datadog/` (or its `adk/` sibling, per design), a
  `Consulted` collector beside `Retrieved`, with unit tests for each.
- Changed: `investigation/contract.py` (a diagnosis value, a confidence level,
  `Findings.consulted`), `ports/investigator.py` (return type),
  `adapters/adk/investigator.py` (routing replaces the walk),
  `adapters/adk/agent.py` (a manager built over agent-tools),
  `triage/domain/report.py` (the body it no longer builds),
  `app/composition.py` (`SIGNALS_EXAMINED` no longer threaded), and the live
  credential-gated check.
- No new dependency, no new configuration key, no ledger change, no CLI change,
  and nothing a notification channel sees.
- Cost per incident falls for incidents needing one or two signals and is
  unchanged at worst, plus two reasoning calls that reach no platform.

## Out of Scope

- **Configurable circuit breakers.** Slice 12 owns `max_tool_calls_per_agent`
  and the question of whether one key can bound both a specialist's searches
  and a manager's consultations. This slice states the budget in code, as slice
  7 did for the MCP timeouts, and leaves the operator setting alone.
- **A model of the Diagnostician's or the Report agent's own.** Both take the
  deployment's default, exactly as the four specialists do, for the reason
  slice 8 gave: the evaluation harness exists to replace guesses like it with
  numbers.
- **Grading the routing.** The evaluation harness's. This slice makes the
  routing observable —
  which specialists were offered, which were consulted — which is what a grader
  needs and does not yet have.
- **Concurrent consultation.** Specialists are consulted one at a time; the
  shared evidence store still numbers retrievals sequentially.
- **Acknowledgement, escalation, and the README diagram.** Slices 11, 14 and 15.
