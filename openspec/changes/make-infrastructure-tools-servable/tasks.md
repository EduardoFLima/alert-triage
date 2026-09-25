Each task is one red / green / refactor cycle. The test named in a task is
written first and watched fail before the code that satisfies it exists.
Test files are named for the behaviour they establish and live at the mirror
of the module's own path, per AGENTS.md.

Task 1 is diagnosis and runs against the real platform, because which tool is
refused is a fact about the platform and cannot be established from a fake.
Task 2 makes a refusal survivable, which is worth doing whatever task 1 finds.
Task 3 acts on the diagnosis. Task 4 is the check that stops the class of
defect recurring.

## 1. Which tool the platform refuses

- [ ] 1.1 In the credential-gated suite, offer each of the infrastructure
  specialist's tools to the real model platform on its own and record which
  are served and which are refused, with the refusal's own words.
- [ ] 1.2 Record the result in this file: the refused tools by name, and
  whether the branching is one tool's or shared across the Kubernetes toolset.
  The next two tasks are written against what this says.

## 2. A refusal is an absent signal, not a failed consultation

- [ ] 2.1 In `tests/unit/investigation/adapters/adk/`, assert that a specialist
  whose model platform refuses one tool is still consulted, with the tools that
  remain. Catch the refusal where tools are offered.
- [ ] 2.2 Assert the refused tool's signal is reported as an empty result
  rather than a failed retrieval, matching how an unconfigured toolset is
  already treated.
- [ ] 2.3 Assert the refusal is recorded where an operator will see it — the
  same place a toolset a deployment did not configure is recorded — naming the
  tool and the platform's reason.
- [ ] 2.4 Assert a specialist whose every tool is refused is still consulted
  and reports nothing, rather than failing the investigation.

## 3. The refused tools, made servable

- [ ] 3.1 Narrow what the refused tools declare to the arguments the
  instruction actually tells the model to pass — for a workload search, its
  cluster, namespace and name. Assert in a unit test that the declared schema
  no longer carries the branching task 1 named.
- [ ] 3.2 Re-run the live offer from 1.1 and record whether the narrowed tools
  are now served.
- [ ] 3.3 Where narrowing was not enough, remove the tool from
  `INFRASTRUCTURE_TOOLS` and from the instruction that names it, and say in the
  docstring which live run decided it. A tool declared but never servable is
  the state this change exists to leave.
- [ ] 3.4 Assert the instruction names no tool the specialist does not declare,
  so a removal cannot leave the model asked for something it does not have.

## 4. Every specialist reaches its model

- [ ] 4.1 Extend the live check that reaches the real model platform so it
  covers every specialist on the roster, not only the ones already known to
  work, failing with the specialist's name and the platform's reason.
- [ ] 4.2 Run it with credentials and record, per specialist, whether it was
  served. Say plainly which were run and which were not.
- [ ] 4.3 Run one live investigation against a service running on containers
  and confirm the report carries infrastructure findings. This is the symptom
  the change was opened for, so it is the symptom that closes it.
- [ ] 4.4 Run the full gate — `ruff check`, `ruff format --check`, `mypy`,
  `pytest` — and record the result alongside what was and was not run live.
