## Why

A triage report is read by someone who then wants to look at the thing itself,
and today neither half of the report will take them there. An alert's link
points at `https://app.{site}/event/event?id={id}` built from the Events API
v2 identifier, and that page does not open: the route is the legacy one and
expects the old numeric event id, not the opaque string v2 returns. Evidence
has no link at all — `EvidenceItem` has no field for one, so where a platform
payload carries a URL it arrives inside `summary`, which is the entry's
`message` key when it has one and otherwise the whole record JSON-dumped and
cut at 300 characters. `normalisation._shortened` already carries a docstring
about half a URL being worse than none, which is the shape of the problem
written down at the wrong end of it.

Both are the same omission: a link is a field nobody gave these records, so
links live wherever they happen to land.

## What Changes

- **`EvidenceItem` gains `url: str | None`.** The address of the thing itself,
  beside the summary rather than inside it. `None` where the platform offers
  no way to address that item, which stays a legitimate answer.
- **The link is derived by the adapter, never written by the model.** A new
  `investigation/adapters/datadog/links.py` builds it from the payload
  `Retrieved` already kept plus the deployment's site. `LogsFinding` gains no
  field: everything in a specialist's output schema is model-authored, and a
  fabricated URL is worse than a fabricated log line — `resolve()` cannot
  catch it, and a reader will click it. The model keeps citing; the adapter
  keeps reproducing.
- **Links are built at both citation grains.** An item (`call-N/item-M`) gets
  the address of that entry where the payload identifies it; a retrieval
  (`call-N`) gets a Log Explorer query link for the query that produced it and
  the window it ran over. This is why `evidence_kept` stops discarding the
  tool `args` it is already handed — the query is in them.
- **`Retrieved` takes a linker.** A callable injected at construction, so
  `adk/` stays framework-only and platform URL knowledge stays in `datadog/`.
  A `Retrieved` built without one keeps every item's `url` at `None`, which is
  what the existing unit tests describe.
- **An alert links to its monitor.** `https://app.{site}/monitors/{monitor_id}`
  scoped to the incident's window, from `attributes.attributes.monitor_id` —
  an integer the payload already carries and a route that has been stable for
  years. An alert with no monitor id falls back to an Event Explorer query
  link over the service and window rather than to a URL known not to open.
- **The report renders a link as a link.** An evidence line carries its
  address on its own line rather than embedded in prose, so what a reader sees
  is the retrieved line and, under it, where to go and see it.
- **A credential-gated check that the URLs resolve.** The live run this project
  already gates on credentials gains an assertion that a built alert URL and a
  built evidence URL answer rather than 404. No fake can establish this, and it
  is precisely what was never established about the URL being replaced.

## Capabilities

### New Capabilities

None. Evidence, alert translation, and what a report carries are all
specified already; each is missing the address of the thing it describes.

### Modified Capabilities

- `investigation`: the evidence normalisation requirement lists an identifier,
  an instant, and a summary; it gains an address, and gains the constraint
  that the address is derived from what was retrieved rather than produced by
  the reasoning that formed the finding — the same line the requirement
  already draws around evidence itself, drawn around its link.
- `alert-ingestion`: the translation requirement says an alert's link comes
  from "the platform's URL for that alert", which is satisfied by a URL that
  does not open. It gains the requirement that the link resolves to a page a
  human can open, built from an identifier whose address form the platform
  supports.
- `triage-run`: the report requirement says the body carries "the links back
  to the platform"; it gains that the evidence carries its own links too, and
  that a link is rendered so it survives the channels a report is delivered
  through.

## Impact

- Changed: `investigation/contract.py` (`EvidenceItem.url`),
  `investigation/adapters/adk/normalisation.py` and `evidence.py` (build and
  thread the link, retain the tool args), `triage/adapters/datadog/alert_source.py`
  (the monitor URL), `triage/domain/report.py` (render it), and the composition
  root (hand the site to the linker).
- New: `investigation/adapters/datadog/links.py`, with unit tests beside it.
- No new dependency, no new configuration key, no CLI change, no ledger change,
  and no change to what the investigator port takes or returns. The site is
  already resolved in composition for `mcp_endpoint`.
- `EvidenceItem` gains a field with a default, so every existing construction
  of one keeps compiling.

## Out of Scope

- **Per-log permalinks that depend on a log id format Datadog does not
  document.** Where the payload names an entry the link uses it; where it does
  not, the item falls back to its retrieval's query link. Chasing an
  undocumented format is how the broken alert URL got written.
- **Links for the other specialists.** Slice 8 adds APM, trace, and
  infrastructure declarations, and their evidence will want addresses of its
  own. The linker is a callable taking a payload precisely so that arrives as
  a body to write rather than a boundary to find, but nothing here builds a
  trace or metric URL.
- **Rendering reports as HTML, or making Teams cards clickable.** The report
  body is plain text carried verbatim by every channel. A URL on its own line
  is auto-linked by mail clients and by Adaptive Cards; changing the body's
  format is report-formatting work that `docs/vision.md` puts in a later slice.
- **Making `summary` smarter.** Widening `SUMMARY_KEYS` or teaching
  normalisation about Datadog's log shape is a separate argument. This change
  gives the link somewhere to live; it does not renegotiate what the summary
  says.
