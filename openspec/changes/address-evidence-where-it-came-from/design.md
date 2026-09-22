## Context

See proposal.md for why. Two constraints from the change that introduced links
still hold and shape everything below.

The linker is **injected, not imported**: `adk/` is the framework's side and
`datadog/` is the platform's, and `test_architecture.py` enforces that the
framework adapter never imports the platform one. Nothing here takes that
import.

The address is **derived, never authored**: a specialist cites, the adapter
reproduces. `resolve()` catches an invented citation and has no equivalent for
an invented URL, which is why `EvidenceItem.url` exists and no output schema
has a field for one. Routing by tool changes where an address points, not who
computes it — and the one place below where the reasoning does contribute, it
contributes a member of a closed set rather than text, for the same reason
`Confidence` is an enum and not a sentence.

## Goals / Non-Goals

**Goals:**

- No retrieval addressed as a kind of thing it did not come from. That is the
  gate, and it is satisfied by answering `None` before it is satisfied by
  answering well.
- A place to add the next tool's address form that is one function and one
  entry, so adding one is not a redesign.
- A live check that fails by specialist name, rather than one that exercises
  the only specialist already correct.

**Non-Goals:**

- Per-item addresses working live. They do not today for reasons this change
  does not touch — the MCP envelope is not unwrapped — and `to_item` stays
  unit-tested only.
- Any change to `EvidenceItem`, to which tools a specialist declares, or to who
  composes an address. `Finding` does gain an enumerated section and the report
  does render a second link; both are bounded additions with defaults, not a
  renegotiation of where addresses come from.
- The retrieved query in an APM or trace address. Deliberately deferred — see
  the decision below.

## Decisions

**The tool's name is threaded through the `Links` protocol.**
`to_retrieval(tool, args)` and `to_item(tool, payload, within)`. The name is
already in hand at the only call site — `_kept` computes `named_tool(tool)` two
lines above `retain_evidence` and uses it for the permitted-tools check — so
this is an argument passed, not a fact discovered. The alternative considered
and rejected is sniffing the arguments: a payload carrying `query`, `from` and
`to` is a log search *or* an error-tracking search *or* an audit search, and a
guess that is right today is a wrong page later with nothing to catch it.

**An unknown tool answers `None`, and that is the gate.** `DatadogLinks` holds
a mapping from tool name to address form, and anything absent from it gets no
address. This is the whole of the correctness claim: after it, a reader is
never sent somewhere the evidence did not come from. Every address form after
that is an improvement on silence. The alternative — holding the change until
every tool the crew reaches has a verified form — keeps a known-wrong link in
production for the length of that work, and ties the fix to the slowest form to
verify.

**Each address form is its own cycle and its own live check.** The Log Explorer
form already exists and is already confirmed against a real account; it is
narrowed to `search_datadog_logs` and `analyze_datadog_logs` rather than
rewritten. The others are written one at a time and each is required to answer
rather than 404, exactly as the log form was. A form that cannot be confirmed
is not shipped, and its tools stay linkless — which the gate makes a safe
outcome rather than a blocking one.

**The APM and trace forms carry the service and the window, and no query.**
The grammars do agree — the Trace Explorer's query language is the same family
as the Log Explorer's, and `search_datadog_spans` takes a query in it — so
copying the retrieved query the way the log form does was the obvious move.
Three things about it are unconfirmed and none is worth the risk: what the tool
calls its query argument, what the explorer calls its parameters, and how a
span-level query resolves on a trace-level view, which lists traces containing
a matching span rather than the spans themselves. A service scope means the
same thing on either view and is a fact the investigation already holds, so the
forms are composed from `InvestigationTarget` rather than read out of `args`.
The retrieved query can be added later against evidence that these links get
followed at all; nothing here forecloses it.

**A finding may choose a section; it may not write an address.** The service
page has tabs, and which one a finding concerns is a judgement only the
reasoning can make — an infrastructure finding about a rollout belongs under
`#infrastructure`. So `Finding` gains an optional section drawn from an
enumerated set, and the adapter composes the address around it. This is a real
amendment to the discipline and is worth stating as one: what makes it
admissible is that a closed set is checkable exactly as a confidence level is,
the system still owns host, path, service, window and every parameter, and the
worst outcome is the right page with the wrong tab open. Free text was
considered and rejected for the reason the requirement already gives — nothing
could check it, and a reader would follow it.

**The anchored address is composed at render time, not at retrieval time.**
`retain_evidence` runs in `after_tool_callback`, before any finding exists, so
it cannot know a section. Evidence therefore keeps its own retrieval address as
today, and the finding's service-page address is built where the report is
built, from the service, the window and the section. Two addresses with two
jobs: where this evidence came from, and where to go and look at the service.
The alternative — deferring every address until findings return — would move
work out of the callback that has been the seat for this since the port was
retired, for no gain to the evidence addresses that are already right.

**The Event Explorer form is not shared with `triage`.**
`triage/adapters/datadog/alert_source.py` already builds one, and the two will
be similar. They stay separate: `shared/` holds vocabulary that depends on no
context and a Datadog route is platform knowledge, not vocabulary; and the two
contexts keeping their own Datadog adapters is the boundary this project
enforces rather than a duplication it overlooked. A URL form is a few lines,
and the cost of sharing it is an edge the architecture test exists to forbid.

**The live check is parameterised over the crew.** It currently resolves
`call-1` from `LOGS_SPECIALIST`, which is the one specialist whose address was
right. Parameterising it the way
`test_every_declared_tool_exists_and_the_filter_admits_it` already is makes the
bug this change fixes the kind of thing that fails by name. A specialist whose
tools have no address form yet asserts that it has none, rather than skipping —
absence is the specified behaviour, so it is assertable.

## Risks / Trade-offs

- **Evidence gets fewer links before it gets better ones.** Three specialists
  go from a wrong address to no address on the first cycle. → That is the
  intended direction, and the report already renders evidence without an
  address. A reader who followed a link to an empty Log Explorer learned
  something false; a reader with no link learns only that there is no link.
- **The mapping is a place for a tool to be forgotten.** A specialist widened
  later reaches a tool with no entry and its evidence quietly loses its
  address. → Quietly, but correctly. Worth a test that every tool the crew
  declares is either mapped or deliberately absent, so the forgetting is
  visible in a unit test rather than in a report.
- **A Datadog UI route changes and a form rots.** → Same exposure as today, and
  the live check is the detector. Parameterising it over the crew widens what
  the detector covers.
- **Verifying a form costs a live retrieval per specialist.** → The run already
  costs a model call and several platform calls per specialist for the
  declaration check. These ride on retrievals that run anyway.

## Migration Plan

None. No stored data carries an evidence address — evidence lives for the
length of one investigation, and the ledger persists `Alert.link` rather than
`EvidenceItem.url`. Reports already sent keep whatever they said.

## Open Questions

- **Which explorer each remaining tool's evidence belongs in**, and whether
  every one of them has an addressable view at all. A metric query and a
  Kubernetes workload plainly do; a catalogue search or a rollout analysis may
  be a view with no shareable address, in which case the honest answer is the
  `None` the gate already provides for.
- **Whether a retrieval's window survives into every explorer's query string
  under the same parameter names** `links._window` already reads. It was
  written against the log tools' argument names, and the `FROM_KEYS` / `TO_KEYS`
  lists exist because tools disagree about them. A form whose window cannot be
  read lands a reader on the right view over the wrong period, which is the
  failure `_window` already refuses by dropping both ends — worth confirming it
  still refuses that way per form.
