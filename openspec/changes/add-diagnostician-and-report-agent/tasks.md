Red / green / refactor throughout, one cycle per behaviour. Every test below is
written failing and watched fail before the code that satisfies it exists.

## 1. The gate: a specialist's structured report survives the agent-tool hop

Done first because everything after it assumes findings can be collected where
design.md says they are collected, and because a seat that turns out to be wrong
is cheaper to discover before six modules depend on it.

- [ ] 1.1 Write a failing unit test in `tests/unit/investigation/adapters/adk/`
      driving the manager's `after_tool_callback` with the payload shape a
      specialist's `AgentTool` yields, asserting the surviving findings are
      collected and the result is handed on unchanged.
- [ ] 1.2 Write a failing unit test that a payload the callback cannot read
      contributes no findings, records the specialist as consulted, and does not
      raise — a specialist that said nothing legible is not a crashed run.
- [ ] 1.3 Implement the callback against `findings_from` and watch both pass.
      Confirm `Retrieved`, the evidence callbacks and `findings_from` were not
      edited; if one had to be, stop and record why in design.md before
      continuing — that is the gate failing.

## 2. What an investigation returns

- [ ] 2.1 Failing test that `Findings` carries `consulted`, defaulting to empty,
      and that an empty tuple is distinguishable from a tuple naming every
      signal. Add the field to `investigation/contract.py`.
- [ ] 2.2 Failing test for a `Confidence` level enum with declared members, and
      that a value outside the set is not one. Add it.
- [ ] 2.3 Failing test for the `Diagnosis` value: it carries a single-line
      headline, an account, an optional hypothesis, an optional confidence, and
      the findings; and it rejects a headline spanning more than one line, as
      `TriageReport` already rejects a multi-line subject.
- [ ] 2.4 Failing test that a `Diagnosis` with no surviving findings carries no
      hypothesis and no confidence, however plausible the reasoning was — assert
      the construction path drops them rather than trusting the caller.
- [ ] 2.5 Change `Investigator.investigate` to return `Diagnosis`, and update
      `tests/unit/investigation/ports/` for the new return. Watch the pipeline's
      existing tests fail on the signature before fixing them in section 7.

## 3. The consultation record

- [ ] 3.1 Failing tests for a `Consulted` collector: it knows which specialists
      it was offered, records which were consulted in order, accumulates the
      findings that survived, and reports the signals consulted with no
      duplicates.
- [ ] 3.2 Failing test that `Consulted` and `Retrieved` are independent — an
      investigation that retrieved evidence for a specialist whose findings were
      all discarded still records that specialist as consulted.
- [ ] 3.3 Implement `Consulted` beside `Retrieved`. Green.

## 4. The ceiling

- [ ] 4.1 Failing test that a consultation beyond `len(crew)` is refused in the
      manager's `before_tool_callback`, the refusal is recorded, and the
      specialist is not run.
- [ ] 4.2 Failing test that the refusal text states the consultation did not
      happen and cannot be read as a specialist reporting nothing — assert
      against the wording, as the `RETRIEVAL_FAILED` tests already do.
- [ ] 4.3 Failing test that an incident needing every declared specialist can
      consult every one of them without being refused.
- [ ] 4.4 Implement the ceiling from the crew's own size. Green.

## 5. The two reasoners

- [ ] 5.1 Failing tests for a `Reasoner` declaration in
      `investigation/domain/`: name, instruction, output schema, optional model;
      rejects an empty name and an empty instruction; and needs no toolset,
      which `Specialist` still refuses. Implement it.
- [ ] 5.2 Failing tests for the Diagnostician declaration's instruction: consult
      only the signals this incident needs; choose the next specialist from what
      the last one reported; reason across the findings rather than restating
      one; state a confidence level from the declared set; conclude on what is
      already gathered when a consultation is refused; never name evidence it
      was not shown; recommend no action.
- [ ] 5.3 Failing test that the Diagnostician's output schema offers no field an
      agent could write evidence into, and that its confidence field admits only
      the declared levels.
- [ ] 5.4 Create the Diagnostician declaration satisfying 5.2 and 5.3.
- [ ] 5.5 Failing tests for the Report agent's instruction: write a single-line
      headline and a body explaining the hypothesis, what it rests on, and what
      is worth checking; characterise the evidence and never reproduce it; never
      state a confidence the diagnosis did not; never recommend an action.
- [ ] 5.6 Failing test for the Report agent's output schema — a headline and a
      narrative, and no field for evidence. Create the declaration.

## 6. Routing

- [ ] 6.1 Failing test that `AdkInvestigator` offers every crew member to the
      manager and consults only those the manager asks for, driven by a stubbed
      `RunDiagnostician` with no model and no network. Assert both the offered
      set and the consulted sequence.
- [ ] 6.2 Failing test that findings come back naming their own signals, that
      `Findings.consulted` names exactly the specialists consulted, and that a
      declared-but-unconsulted signal appears nowhere in the result.
- [ ] 6.3 Failing test that an investigation consulting nobody returns a
      completed diagnosis with no findings, no consulted signals, and no
      hypothesis — not an `InvestigatorError`.
- [ ] 6.4 Failing test that the existing failure arcs are unchanged: every
      retrieval failing is still an `InvestigatorError`, and some failing still
      returns findings marked incomplete.
- [ ] 6.5 Replace the crew walk in `adapters/adk/investigator.py` with the
      manager, keeping `RunSpecialist` as the thing a consultation drives.
      Green.
- [ ] 6.6 Build the manager over `AgentTool`s in `adapters/adk/agent.py`, with
      the two callbacks from sections 1 and 4 attached. Failing test first that
      the built agent's tools are one per crew member and it reaches no MCP
      toolset of its own.
- [ ] 6.7 Failing test that the Report agent runs after the Diagnostician, over
      the hypothesis and the surviving findings, and that its failure or an
      unusable answer falls back to the deterministically composed account with
      the report still delivered.

## 7. The report

- [ ] 7.1 Move the report-body tests that concern findings, evidence, links and
      incompleteness from `tests/unit/triage/domain/test_what_a_report_says.py`
      to investigation's side, verbatim rather than rewritten, and watch them
      fail where the rendering does not yet live.
- [ ] 7.2 Move the deterministic evidence rendering into investigation, beneath
      the account. Green, with the link-rendering scenarios passing unchanged.
- [ ] 7.3 Failing test that a report of a concluded investigation states the
      hypothesis and the confidence level, and states them as a hypothesis
      rather than a verdict.
- [ ] 7.4 Failing test that a report carrying a hypothesis still carries the
      findings and the evidence beneath them.
- [ ] 7.5 Failing test that a report names exactly the signals consulted, that
      a declared-but-unconsulted signal is not reported as clean, and that an
      investigation consulting nobody is reported as having examined no signal
      rather than as nothing notable.
- [ ] 7.6 Failing test that the last-resort report — every investigation failed
      — carries no hypothesis and no confidence.
- [ ] 7.7 Rewrite `triage/domain/report.py` to take a `Diagnosis`: subject, the
      alert list, and the last-resort report stay; the account arrives written.
      Confirm the module imports no `Finding`, `EvidenceItem` or `Signal`.
- [ ] 7.8 Remove `SIGNALS_EXAMINED` and the `examined=` argument, and drop the
      `partial` in `app/composition.py`. Failing test first that the report's
      claimed scope comes from the investigation rather than from the
      composition root.
- [ ] 7.9 Update `app/pipeline.py`'s `ReportBuilder` for the new argument and
      fix the pipeline tests section 2.5 broke. Confirm the run's ordering,
      cooldown, attempt and delivery behaviour are untouched.

## 8. Live confirmation (credential-gated)

- [ ] 8.1 Extend `tests/integration/investigation/adapters/datadog/` with a live
      check that a real Diagnostician, offered the real crew, consults at least
      one specialist and produces a hypothesis with a declared confidence level.
- [ ] 8.2 Confirm it still skips cleanly with no credentials, as the existing
      live check does.
- [ ] 8.3 Run it against a real account. Establish the gate from section 1
      against the real framework: whether the specialist's structured report
      survives the agent-tool hop, or whether findings must be collected from
      the specialist's own `after_agent_callback` instead. Record the answer in
      design.md.
- [ ] 8.4 Record which specialists the manager consulted and how many
      consultations it made, as the first real evidence for slice 12's
      `max_tool_calls_per_agent` applied to a manager.
- [ ] 8.5 Record whether the manager issued concurrent consultations, which is
      the risk design.md leaves open against the shared evidence store.
- [ ] 8.6 Record whether the Report agent's account reproduced evidence despite
      being told not to. If it did, the deterministic block below it is what
      keeps the report honest — note whether the duplication is bad enough to
      warrant tightening the instruction in slice 10.

## 9. Before calling it done

- [ ] 9.1 `uv run ruff check src tests`
- [ ] 9.2 `uv run ruff format --check src tests`
- [ ] 9.3 `uv run mypy`
- [ ] 9.4 `uv run pytest`
- [ ] 9.5 Confirm the architecture test still passes with no `.importlinter`
      edit. Triage should now import *less* of investigation's vocabulary, not
      more; a contract change here would mean the report move landed in the
      wrong context.
- [ ] 9.6 Confirm `README.md` and `docs/configuration.md` say nothing that the
      moved report rendering or the concluded report has made untrue. The
      architecture diagram is deliberately left alone — slice 15.
- [ ] 9.7 Archive `add-remaining-specialists` before archiving this change: its
      `A report says which signals were examined` is what section 7's delta
      modifies. See design.md, Migration Plan.
