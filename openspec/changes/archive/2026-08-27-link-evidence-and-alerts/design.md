## Context

See proposal.md for why. Two constraints shape everything below.

The first is the evidence discipline `investigation/domain/evidence.py` states:
a specialist cites, the adapter reproduces, and nothing the model writes reaches
a report as evidence. A link is evidence about evidence, and it is the part a
reader acts on, so it falls inside that line rather than outside it.

The second is the axis split inside `investigation/adapters/`: `adk/` is the
framework and `datadog/` is the platform. Building a Datadog URL is platform
knowledge. `adk/crew.py` already imports from `adapters/datadog/`, so nothing
in `.importlinter` forbids `evidence.py` doing the same — but the direction
that import would establish is the wrong one, and this design does not take it.

## Goals / Non-Goals

**Goals:**

- One field on `EvidenceItem`, populated in one place, rendered in one place.
- A URL builder whose inputs are the retained payload and the deployment's
  site, so it is a pure function a unit test drives with a dict.
- An alert URL built from an identifier whose address form is not a guess, and
  a live check that says so.

**Non-Goals:**

- Any change to the `Investigator` port, the contract's `Finding`, or what a
  specialist declares. If a link needs a specialist edited, it has been put on
  the wrong side of the discipline.
- Teaching `normalisation` about Datadog. It stays shallow and platform-blind;
  the link arrives through an injected callable, not a widened key list.

## Decisions

**`EvidenceItem.url` rather than a field on `LogsFinding`.** The output schema
is model-authored, and `resolve()` is what catches an invented citation — it
has no equivalent for an invented URL, which resolves to nothing and is
indistinguishable from a real one until a reader follows it. Worse, the model
never sees a URL to copy: `Retrieved` hands it `id`, `instant`, `summary` and
`data`, so anything URL-shaped in a finding would be confabulated by
construction. The alternative — an `evidence_url` the model fills from the
payload — moves the one field a reader trusts most into the one place this
project trusts least.

**The linker is a callable injected into `Retrieved`, not an import.**
`Retrieved.__init__` takes `link: Linker | None = None` where `Linker` is
`Callable[[Any], str | None]`, and `normalisation._item` takes it as an
argument. The Datadog implementation lives in
`investigation/adapters/datadog/links.py` and is bound to a site by
`AdkInvestigator`'s construction, which composition already supplies alongside
`mcp_endpoint(site)`. The alternative, importing the builder into `evidence.py`,
would make the framework adapter depend on the platform adapter for something
that is not a specialist declaration, and would leave a second platform's logs
specialist unable to bring its own URLs. Defaulting to `None` keeps every
existing `Retrieved()` construction and its tests untouched.

**The retrieval's link is built from the tool args, which are already handed
over.** `evidence_kept`'s `_kept` receives `args` and drops them. An aggregate
has no discrete item to address, so its link has to be the query link, and the
query is exactly what `args` carries. `Retrieved.retain` gains the args
alongside the result. The alternative — recovering the query from the result —
depends on the platform echoing it back, which Datadog does not reliably do.

**The alert links to its monitor.** `attributes.attributes.monitor_id` is an
`int` in the SDK model and `/monitors/{id}` is a route that predates the v2
Events API; `from_ts`/`to_ts` scope it to the incident's window so the link
still shows the firing days later. The alternative kept in reserve, and used
when there is no monitor id, is an Event Explorer query link over the service
and window. What is not kept is `/event/event?id={id}`: `EventResponse.id` is
declared `str` in v2 and that route is the v1 numeric page, which is the whole
bug.

**Nothing ships on an unverified URL format.** The credential-gated live test
gains one assertion per URL form: build it, request it, and require an answer
rather than a 404. This is the only mechanism that would have caught the URL
being replaced, and it is cheap — two HTTP requests on a run that already costs
model calls. A unit test can only assert the string, which is what the current
tests do and why they pass against a broken link.

**A link is rendered on its own line, below the evidence line.**
`report._evidence_line` returns one string today; it becomes a small list, and
`_finding_lines` extends rather than appends. Putting the URL after the summary
on the same line would put it inside the text `_shortened` truncates, which is
the failure the report is being fixed for. Plain text on its own line is
auto-linked by mail clients and by Adaptive Card text blocks, so no channel
needs to change.

**Per-item addressing is best-effort and falls back to the retrieval's link.**
Where a retrieved log entry carries an id the payload names, the item's link
addresses that entry; where it does not, the item inherits the query link for
the retrieval it came from, which lands a reader on the right search rather
than nowhere. Chasing an undocumented per-log address format is the mistake
this change exists to undo, so the fallback is the default and the specific
case is the optimisation.

## Risks / Trade-offs

- **Datadog changes a UI route and every link rots silently.** → The live check
  is the detector, and it names the URL form that failed. This is a smaller
  blast radius than today, where nothing checks at all.
- **`monitor_id` is absent on some alert events.** → The SDK types it as
  `(int, none_type)`, so absence is expected, not exceptional; the Event
  Explorer fallback covers it and gets its own unit test. An alert whose link
  cannot be built at all keeps `Alert.link`'s empty default, which
  `report.NO_LINK` already renders.
- **The live check needs an account whose monitor and logs actually exist.** →
  It asserts the URL answers, not that it shows a particular incident. A 404
  is the signal; an empty-but-valid page is a pass, and a stricter check would
  be flaky for no gain.
- **`EvidenceItem` gains a field and every construction site grows.** → It has
  a default of `None`, and the two places that build one — `normalisation._item`
  and `Retrieved.retain`'s call-level item — are the only ones that pass it.
- **Two grains of link means two code paths and a fallback between them.** →
  The fallback is one expression, and the unit tests cover an item with an
  addressable id, an item without one, and an aggregate.

## Migration Plan

None. No stored data carries a link — the ledger persists `Alert.link` per
incident, so incidents recorded before this change keep the broken URL until
they are closed and deleted by the existing retention policy. Backfilling them
is not worth a migration: the cooldown and retention windows are measured in
days, and a report is sent once.

## Open Questions

- Whether Datadog's log payloads through MCP carry an entry id under a key
  stable enough to address individual logs by. The fallback makes this a
  question about link precision rather than about whether links work, and the
  live run answers it by showing what a real payload contains.
