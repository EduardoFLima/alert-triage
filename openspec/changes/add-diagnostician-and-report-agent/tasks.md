Red / green / refactor throughout, one cycle per behaviour. Every test below is
written failing and watched fail before the code that satisfies it exists.

## 1. The gate: a specialist's structured report survives the agent-tool hop

Done first because everything after it assumes findings can be collected where
design.md says they are collected, and because a seat that turns out to be wrong
is cheaper to discover before six modules depend on it.

- [x] 1.1 Write a failing unit test in `tests/unit/investigation/adapters/adk/`
      driving the manager's `after_tool_callback` with the payload shape a
      specialist's `AgentTool` yields, asserting the surviving findings are
      collected and the result is handed on unchanged.
- [x] 1.2 Write a failing unit test that a payload the callback cannot read
      contributes no findings, records the specialist as consulted, and does not
      raise — a specialist that said nothing legible is not a crashed run.
- [x] 1.3 Implement the callback against `findings_from` and watch both pass.
      Confirm `Retrieved`, the evidence callbacks and `findings_from` were not
      edited; if one had to be, stop and record why in design.md before
      continuing — that is the gate failing. (Behaviour untouched. The one edit
      is a rename: `_named` became `named_tool`, since the consultation
      callbacks sit on the same seat and need the same answer.)

## 2. What an investigation returns

- [x] 2.1 Failing test that `Findings` carries `consulted`, defaulting to empty,
      and that an empty tuple is distinguishable from a tuple naming every
      signal. Add the field to `investigation/contract.py`.
- [x] 2.2 Failing test for a `Confidence` level enum with declared members, and
      that a value outside the set is not one. Add it.
- [x] 2.3 Failing test for the `Diagnosis` value: it carries a single-line
      headline, an account, an optional hypothesis, an optional confidence, and
      the findings; and it rejects a headline spanning more than one line, as
      `TriageReport` already rejects a multi-line subject.
- [x] 2.4 Failing test that a `Diagnosis` with no surviving findings carries no
      hypothesis and no confidence, however plausible the reasoning was — assert
      the construction path drops them rather than trusting the caller.
- [x] 2.5 Change `Investigator.investigate` to return `Diagnosis`, and update
      `tests/unit/investigation/ports/` for the new return. Watch the pipeline's
      existing tests fail on the signature before fixing them in section 7.

## 3. The consultation record

- [x] 3.1 Failing tests for a `Consulted` collector: it knows which specialists
      it was offered, records which were consulted in order, accumulates the
      findings that survived, and reports the signals consulted with no
      duplicates.
- [x] 3.2 Failing test that `Consulted` and `Retrieved` are independent — an
      investigation that retrieved evidence for a specialist whose findings were
      all discarded still records that specialist as consulted.
- [x] 3.3 Implement `Consulted` beside `Retrieved`. Green.

## 4. The consultation budget

- [x] 4.1 Failing test that the budget counts consultations rather than
      specialists: the same specialist consulted twice with different questions
      spends two of it and is refused neither time.
- [x] 4.2 Failing test that a consultation beyond the budget is refused in the
      manager's `before_tool_callback`, the refusal is recorded, and the
      specialist is not run.
- [x] 4.3 Failing test that the refusal text states the consultation did not
      happen and cannot be read as a specialist reporting nothing — assert
      against the wording, as the `RETRIEVAL_FAILED` tests already do.
- [x] 4.4 Failing test that an incident needing every declared specialist
      consults every one of them without being refused, and still has
      consultations left for their follow-up questions.
- [x] 4.5 Failing test that an investigation which hit the budget still
      concludes on the findings it gathered before the refusal, and is reported
      as having been cut short rather than as having chosen to stop.
- [x] 4.6 Implement the budget as a stated constant of 8, documented as what
      `docs/vision.md`'s `max_tool_calls_per_agent` means for a manager whose
      tools are specialists, and as slice 12's to read from configuration.
      Green.

## 5. The two reasoners

- [x] 5.1 Failing tests for a `Reasoner` declaration in
      `investigation/domain/`: name, instruction, output schema, optional model;
      rejects an empty name and an empty instruction; and needs no toolset,
      which `Specialist` still refuses. Implement it.
- [x] 5.2 Failing tests for the Diagnostician declaration's instruction: consult
      only the signals this incident needs; choose the next specialist from what
      the last one reported; go back to a specialist with a narrower question
      where its answer raised one, spending the budget on questions worth
      asking; reason across the findings rather than restating one; state a
      confidence level from the declared set; conclude on what is already
      gathered when a consultation is refused; never name evidence it was not
      shown; recommend no action.
- [x] 5.3 Failing test that the Diagnostician's output schema offers no field an
      agent could write evidence into, and that its confidence field admits only
      the declared levels.
- [x] 5.4 Create the Diagnostician declaration satisfying 5.2 and 5.3.
- [x] 5.5 Failing tests for the Report agent's instruction: write a single-line
      headline and a body explaining the hypothesis, what it rests on, and what
      is worth checking; characterise the evidence and never reproduce it; never
      state a confidence the diagnosis did not; never recommend an action.
- [x] 5.6 Failing test for the Report agent's output schema — a headline and a
      narrative, and no field for evidence. Create the declaration.

## 6. Routing

- [x] 6.1 Failing test that `AdkInvestigator` offers every crew member to the
      manager and consults only those the manager asks for, driven by a stubbed
      `RunDiagnostician` with no model and no network. Assert both the offered
      set and the consulted sequence.
- [x] 6.2 Failing test that findings come back naming their own signals, that
      `Findings.consulted` names exactly the specialists consulted, and that a
      declared-but-unconsulted signal appears nowhere in the result.
- [x] 6.3 Failing test that an investigation consulting nobody returns a
      completed diagnosis with no findings, no consulted signals, and no
      hypothesis — not an `InvestigatorError`.
- [x] 6.4 Failing test that the existing failure arcs are unchanged: every
      retrieval failing is still an `InvestigatorError`, and some failing still
      returns findings marked incomplete.
- [x] 6.5 Replace the crew walk in `adapters/adk/investigator.py` with the
      manager, keeping `RunSpecialist` as the thing a consultation drives.
      Green.
- [x] 6.6 Build the manager over `AgentTool`s in `adapters/adk/agent.py`, with
      the two callbacks from sections 1 and 4 attached. Failing test first that
      the built agent's tools are one per crew member and it reaches no MCP
      toolset of its own.
- [x] 6.7 Failing test that the Report agent runs after the Diagnostician, over
      the hypothesis and the surviving findings, and that its failure or an
      unusable answer falls back to the deterministically composed account with
      the report still delivered.

## 7. The report

- [x] 7.1 Move the report-body tests that concern findings, evidence, links and
      incompleteness from `tests/unit/triage/domain/test_what_a_report_says.py`
      to investigation's side, verbatim rather than rewritten, and watch them
      fail where the rendering does not yet live.
- [x] 7.2 Move the deterministic evidence rendering into investigation, beneath
      the account. Green, with the link-rendering scenarios passing unchanged.
- [x] 7.3 Failing test that a report of a concluded investigation states the
      hypothesis and the confidence level, and states them as a hypothesis
      rather than a verdict.
- [x] 7.4 Failing test that a report carrying a hypothesis still carries the
      findings and the evidence beneath them.
- [x] 7.5 Failing test that a report names exactly the signals consulted, that
      a declared-but-unconsulted signal is not reported as clean, and that an
      investigation consulting nobody is reported as having examined no signal
      rather than as nothing notable.
- [x] 7.6 Failing test that the last-resort report — every investigation failed
      — carries no hypothesis and no confidence.
- [x] 7.7 Rewrite `triage/domain/report.py` to take a `Diagnosis`: subject, the
      alert list, and the last-resort report stay; the account arrives written.
      Confirm the module imports no `Finding`, `EvidenceItem` or `Signal`.
- [x] 7.8 Remove `SIGNALS_EXAMINED` and the `examined=` argument, and drop the
      `partial` in `app/composition.py`. Failing test first that the report's
      claimed scope comes from the investigation rather than from the
      composition root.
- [x] 7.9 Update `app/pipeline.py`'s `ReportBuilder` for the new argument and
      fix the pipeline tests section 2.5 broke. Confirm the run's ordering,
      cooldown, attempt and delivery behaviour are untouched.

## 8. Live confirmation (credential-gated)

- [x] 8.1 Extend `tests/integration/investigation/adapters/datadog/` with a live
      check that a real Diagnostician, offered the real crew, consults at least
      one specialist and produces a hypothesis with a declared confidence level.
- [x] 8.2 Confirm it still skips cleanly with no credentials, as the existing
      live check does.
- [x] 8.7 First live run, and what it found. The specialist's structured report
      did survive the agent-tool hop — three findings were collected and checked
      — so the section 1 gate holds. Two other things did not. Wrapping a
      specialist as an agent-tool with `skip_summarization` makes its *result*
      event report `is_final_response()`, so reading the last final event
      overwrote the manager's conclusion with an empty record; `answer_in` now
      filters by author and never lets an unreadable event erase an answer. And
      the manager stopped after one specialist — diagnosed twice, wrongly both
      times, and finally understood in 8.9. A manager that answers with no
      conclusion at all is now a warning rather than silence.
- [x] 8.8 A specialist answered in prose where its schema was asked for, and
      `AgentTool` validated it and raised. ADK catches a tool error, offers it to
      `on_tool_error_callback`, and re-raises when nobody answers — so one
      specialist's bad turn ended the whole investigation and took every other
      specialist's findings with it. The manager now carries that callback: a
      failed consultation is answered in the same terms as a refused one, kept
      to the consultation that had it, and recorded so the report says the
      investigation was incomplete. A failure in anything that is not a
      specialist is still left to raise.
- [x] 8.9 The real cause of the stop, and the correction of two wrong
      diagnoses. Wrapping each specialist with `skip_summarization=True` was the
      whole of it. That sets the flag on the consultation's *result* event,
      `Event.is_final_response` reports any such event as final, and the
      framework's turn loop runs `while True` until the last event is final. So
      the manager's turn ended the instant its first specialist answered: never
      called again, unable to consult a second, unable to reason across
      anything, unable to produce its schema at all.

      That is why neither instruction rewrite changed a thing — no wording
      reaches a model that is never asked again — and it is the fault behind
      every routing symptom in 8.7. Skipping summarisation was asked for to get
      the specialist's raw structured answer; it costs the whole conversation
      and buys nothing, because the report is collected in
      `after_tool_callback` before the model does anything with it. Specialists
      are now wrapped plainly.

      What the two wrong diagnoses claimed, for the record. The first blamed an
      instruction ADK injects with its `set_model_response` workaround — which
      is never created on Vertex, where a Gemini model pairs an output schema
      with tools natively, so that path was never taken. The second blamed the
      native response schema making the conclusion cheap on every turn, and
      answered it by asking the manager again; that machinery is removed, since
      it existed to compensate for a manager that could not continue.

      Two fixes those diagnoses prompted are kept, because they stand without
      them: a failed consultation answered rather than raised, and an answer
      read from its own author's final event.
- [ ] 8.3 Run it again and confirm the three fixes: the manager consults more than
      one specialist where the incident warrants it, a conclusion it reaches
      survives into the report, and a specialist that cannot answer costs its own
      consultation rather than the run. Establish the gate from section 1
      against the real framework: whether the specialist's structured report
      survives the agent-tool hop, or whether findings must be collected from
      the specialist's own `after_agent_callback` instead. Record the answer in
      design.md.
- [ ] 8.4 Record which specialists the manager consulted, how many
      consultations it made, and how many of those were second questions to a
      specialist it had already asked — the first real evidence for whether 8 is
      the right budget and whether re-asking earns its calls.
- [ ] 8.5 Record whether the manager issued concurrent consultations, which is
      the risk design.md leaves open against the shared evidence store.
- [ ] 8.6 Record whether the Report agent's account reproduced evidence despite
      being told not to. If it did, the deterministic block below it is what
      keeps the report honest — note whether the duplication is bad enough to
      warrant tightening the instruction once the evaluation harness can score it.

## 9. Before calling it done

- [x] 9.1 `uv run ruff check src tests`
- [x] 9.2 `uv run ruff format --check src tests`
- [x] 9.3 `uv run mypy`
- [x] 9.4 `uv run pytest`
- [x] 9.5 Confirm the architecture test still passes with no `.importlinter`
      edit. Triage should now import *less* of investigation's vocabulary, not
      more; a contract change here would mean the report move landed in the
      wrong context.
- [x] 9.6 Confirm `README.md` and `docs/configuration.md` say nothing that the
      moved report rendering or the concluded report has made untrue. The
      architecture diagram is deliberately left alone — slice 15.
