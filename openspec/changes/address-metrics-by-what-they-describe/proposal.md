## Why

A metric retrieval is addressed at the service's APM page no matter what the
metric was about. `search_metrics`, `get_metric_context` and `get_metric` are
routed as service-scoped APM tools, and the infrastructure specialist declares
all three — so a finding about container CPU against its request limit is
handed a reader a page of request rates, latencies and error rates. Nothing on
it shows the CPU the finding is about.

This is close to the failure the addressing rule was written to prevent: an
address built for another kind of retrieval opens a page that looks like an
answer, and a reader cannot tell it from a page that is genuinely empty. It
reached a real report, twice in one finding, because the routing asks which
tool was called and stops there — a metric is a metric, and where you go to
look at one depends on what it measures.

## What Changes

- **A metric retrieval opens the metric it retrieved.** Each of the three
  metric tools gets the page that answers for what it fetched: a metric search
  opens the summary of the metrics it matched, a metric's context opens that
  metric's own summary, and a metric query opens the explorer over that query
  and window. The service catalogue keeps the APM entity page, which is what it
  asked about.
- **A template that does not survive a live check is dropped, not shipped.**
  The tool goes back to having no address, which is visibly nothing, rather
  than keeping one that opens the wrong page.
- **An address is absent where the retrieval's own subject cannot be read.** A
  metric query whose metric name cannot be recovered from the call gets no
  address rather than a page scoped to something else.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `investigation`: an address opens a view of what the retrieval was about,
  and is absent rather than opening a view of something else.

## Impact

- `investigation/adapters/datadog/links.py` — `APM_SERVICE_TOOLS` and the
  templates behind it.
- `tests/unit/investigation/adapters/datadog/test_evidence_is_addressed_where_it_lives.py`
- `tests/integration/investigation/adapters/datadog/` — each new template
  confirmed against a real account before it ships.

Out of scope: the per-finding "look at the service" link, which is a different
address with a different job and already opens the section the finding named.
The infrastructure inventory's windowlessness, which is a documented property
of that page rather than a mis-addressing. Reading Datadog's text answers,
which is `read-datadogs-text-answers`.
