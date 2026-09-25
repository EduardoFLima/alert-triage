Each task is one red / green / refactor cycle. The test named in a task is
written first and watched fail before the code that satisfies it exists.
Test files are named for the behaviour they establish and live at the mirror
of the module's own path, per AGENTS.md.

Task 1 is the gate: after it, no metric retrieval is addressed as a page it
did not come from, because the metric tools are addressed by nothing at all.
Tasks 2 to 4 are additive, one template at a time. Task 5 confirms them
against a real account, and a template that fails there is deleted — the tool
stays in `UNADDRESSED`, which is where task 1 left it.

## 1. A metric is no longer a service page

- [ ] 1.1 In `tests/unit/investigation/adapters/datadog/test_evidence_is_addressed_where_it_lives.py`,
  assert a `get_metric` retrieval is not addressed at the service's APM page.
  Take the three metric tools out of `APM_SERVICE_TOOLS` in `datadog/links.py`
  and put them in `UNADDRESSED`, leaving the service catalogue where it is.
- [ ] 1.2 In the same file, assert the service catalogue still opens the APM
  entity page exactly as it does today. It is the one tool in that group that
  asked about the service itself.
- [ ] 1.3 Run the catalogue test that fails when a reachable tool is in neither
  set, and confirm it passes. Every tool the crew reaches is still accounted
  for as addressed or deliberately not.

## 2. A metric query opens its own series

- [ ] 2.1 In the same file, assert a `get_metric` retrieval is addressed at the
  explorer over the query it ran and the window it ran across. Add the template
  and move the tool out of `UNADDRESSED`.
- [ ] 2.2 Assert a `get_metric` call whose metric or query cannot be read from
  its arguments gets no address at all, rather than one scoped to the service.

## 3. A metric search opens what it matched

- [ ] 3.1 Assert a `search_metrics` retrieval is addressed at the summary of
  metrics matching the filter it searched on.
- [ ] 3.2 Assert a `search_metrics` call with no readable filter gets no
  address. A summary scoped to nothing lists every metric in the account, which
  reads as an answer and is not one.

## 4. A metric's context opens that metric

- [ ] 4.1 Assert a `get_metric_context` retrieval is addressed at the summary
  of the metric it described, scoped to that metric by name.
- [ ] 4.2 Assert a call with no readable metric name gets no address.

## 5. Against a real account

- [ ] 5.1 Extend the credential-gated suite so each new template is composed
  from a real retrieval and fetched, asserting the response is not an error.
  One case per template, named for the view it opens.
- [ ] 5.2 Run the suite with credentials and record, per template, whether it
  opened. Note that a non-error response rules out a wrong route but cannot
  prove the view is scoped to the right thing — say which templates were also
  opened by eye.
- [ ] 5.3 Delete any template that did not open, leave its tool in
  `UNADDRESSED`, and say in that docstring which live run decided it. A
  template kept with a note of doubt is the failure this gate exists for.
- [ ] 5.4 Run one live investigation against a service with container metrics
  and read the infrastructure findings in the report: confirm no evidence line
  points at an APM entity page. This is the symptom the change was opened for,
  so it is the symptom that closes it.
- [ ] 5.5 Run the full gate — `ruff check`, `ruff format --check`, `mypy`,
  `pytest` — and say plainly which of 5.2 to 5.4 were run against real
  credentials and which were not.
