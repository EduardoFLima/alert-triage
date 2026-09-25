## Why

`DatadogLinks.to_retrieval` builds a Log Explorer address, and
`Retrieved._address_of` applies it to every retrieval whatever the tool. Three
of the four specialists never touch a log tool, so a metric query, a host
search, a Kubernetes workload and a trace are each addressed as a log search
they did not come from. A metric retrieval carries no `query` key either, so
what a reader is handed is `/logs?query=&live=false` — an empty Log Explorer,
presented under the evidence as where to go and see it.

`links.py` states the principle it is failing: *"A link that degrades to the
right page is the whole point: the broken link this replaced degraded to
nowhere."* It now degrades to somewhere, which is worse — nowhere is visibly
nothing, and the wrong page looks like an answer.

Nothing catches it. The live check resolves `call-1` from the **logs**
specialist only, so the one specialist whose address is right is the only one
tested, and the unit tests assert the string a log payload produces.

## What Changes

- **A retrieval's address is built from the tool as well as its arguments.**
  `Links.to_retrieval` and `Links.to_item` take the tool's name.
  `evidence_kept` already computes it — `named_tool(tool)`, two lines above the
  `retain_evidence` call — so it is threaded, not discovered.
- **A tool with no address template gets no address.** `DatadogLinks` answers
  `None` for anything it cannot place, and `EvidenceItem.url` is already `str |
  None` with a report that renders evidence without one. This is the gate:
  after it, no retrieval is addressed as a page it did not come from, and every
  address template added afterwards is an improvement on silence rather than a
  correction of a lie.
- **The APM and trace specialists get named templates.** APM evidence lands on
  the service's own page — `/apm/entity/service%3A{service}?start=&end=` — and
  trace evidence on the trace explorer scoped to that service,
  `/apm/traces?query=service%3A{service}&start=&end=`. Both are composed from
  the service and the window, which the investigation already holds. Neither
  copies the query the tool was called with: the grammars do match, but the
  tool's argument name, the explorer's parameter names and how a span-level
  query resolves on a trace-level view are each unconfirmed, and a service
  scope means the same thing either way.
- **A finding may say which section of the service page it concerns**, chosen
  from an enumerated set the adapter knows — `#infrastructure` for a workload
  that was rolled out, and so on. The model picks a member; the adapter builds
  every other part of the address. A wrong pick opens the right service page on
  the wrong tab, which is why a bounded choice is admissible here where a
  written address is not.
- **Address templates are added one tool at a time, each confirmed live.** The
  Log Explorer template is kept and narrowed to the log tools. The others are
  written against the explorers their evidence actually lives in, and each is
  checked the way the log template was — built from a real retrieval and
  required to answer rather than 404.
- **The live check stops being about one specialist.** It is parameterised over
  the crew the way the declaration check already is, so a specialist whose
  evidence is addressed wrongly fails by name.

## Capabilities

### New Capabilities

None. `investigation` already requires that evidence carries an address at both
grains; what it does not yet say is that the address opens the thing the
evidence came from.

### Modified Capabilities

- `investigation`: the evidence requirement says a retrieval "SHALL be
  addressed as the query that produced it over the window it ran over", which
  is written in the vocabulary of one tool and satisfied by a log address built
  for a metric. It gains that an address SHALL open the retrieval it was built
  for, and that where the platform's address for a retrieval is not known, the
  evidence SHALL carry no address rather than one built for a different kind of
  retrieval — absence already being a complete answer the requirement accepts.
- `investigation`: the same requirement forbids an address produced by the
  reasoning that formed the finding, on the grounds that an invented address
  cannot be checked. It gains the one admissible exception and the reason it is
  one: a finding MAY choose *where within* an address it concerns, from a set
  the system enumerates, because a choice from a closed set is checkable the
  way a written address is not and a wrong choice degrades to the right page.
  The address itself SHALL still be composed by the system.

## Impact

- Changed: `investigation/adapters/adk/evidence.py` (the `Links` protocol,
  `retain_evidence`, `_address_of`, `_item_addresses`, and the one call site in
  `_kept`), `investigation/adapters/datadog/links.py` (routing by tool, plus a
  template per tool), and their unit tests.
- Changed: `tests/integration/investigation/adapters/datadog/test_every_specialist_reaches_the_real_platform.py`,
  which currently checks one specialist's address.
- Changed: `investigation/contract.py`, where `Finding` gains an optional
  enumerated section — defaulted, so every existing construction keeps
  compiling, the move `EvidenceItem.url` already made — and the specialist
  output schemas that may set it.
- `EvidenceItem.url` is unchanged and already optional. No configuration key,
  no dependency, no ledger change. `adk/` gains no import of `datadog/`: the
  linker still arrives injected, and the architecture test that guards it is
  unchanged.

## Out of Scope

- **Unwrapping the MCP result envelope.** Per-item citations do not resolve
  live at all today, so `to_item` is exercised only by unit tests whatever this
  change does. It is named in `docs/vision.md` under *A Datadog integration
  that holds up* and is a prerequisite for per-item addresses mattering, not
  for retrieval addresses being right.
- **An address template for every tool in the crew.** Each is its own cycle and
  its own live check, and a tool left without one is now correctly linkless.
  The change ships the routing plus the templates that pass their check.
- **Sharing a URL template with `triage`.** The alert source builds its own
  Event Explorer address, and the two contexts keep their own Datadog adapters
  by design — see design.md.
- **How a report renders an address.** Unchanged: its own line, below the
  evidence line, auto-linked by the channels. Evidence with no address renders
  as it already does.
