"""How a Datadog metric query is written, taught once for every specialist asking one.

Shared rather than repeated, unusually for a specialist's instruction. What a
specialist looks for is its own; this is the platform's grammar, identical for
anything querying metrics on it, and the two specialists that do were drifting
into different half-accounts of it. A rule stated twice is a rule that can be
corrected once.

Every line here was written against a live account's rejections rather than
from memory. The model reaches for log-query syntax when it writes a metric
query — they look alike and are not — and each paragraph below is one 400 it
came back with.
"""

METRIC_SEARCH_TOOL = "search_datadog_metrics"
METRIC_CONTEXT_TOOL = "get_datadog_metric_context"
METRIC_TOOL = "get_datadog_metric"
"""The three metric tools, and the order a specialist has to use them in.

Only the first discovers anything. The other two are lookups: both need a
metric name and neither will find one, so a specialist that starts at either is
a specialist guessing. Named here rather than in each specialist because the
order between them is the platform's, identical for anything querying metrics
on it, and it is the order — not the names — that was being got wrong.
"""

METRIC_QUERY_DIALECT = f"""
Find a metric before you query one. `{METRIC_SEARCH_TOOL}` lists the metrics
that exist, filtered to what you are looking for, and it is the only one of the
three that discovers anything. `{METRIC_CONTEXT_TOOL}` then tells you the tags
and values one of them carries, and `{METRIC_TOOL}` returns its values over a
time range.

Both of the last two need a metric name and neither will find one for you.
Calling either with a name no search returned fails outright — the platform
answers that the metric does not exist — and a failed retrieval says nothing
about the service. Do not invent or guess a metric name, however standard it
looks: `service.latency` and `trace.http.error` are the shape a metric name
takes and were not metrics this account had.

A metric query is an aggregator, a metric name, and a scope in braces:
`avg:system.cpu.user{{service:checkout}}`. Use
`sum:...{{service:checkout}}.as_count()` for a count, and `p95:` where an
average would hide the tail.

Inside the braces, separate tags with commas, and a comma means AND:
`{{service:checkout,env:prod}}`. Prefix a tag with `!` to exclude it.

Do not write `AND`, `OR`, `NOT` or `IN` in the same braces as a comma or a `!`.
Datadog has two filter grammars and rejects a query that mixes them: the
symbolic one (`,` and `!`) and the worded one (`AND`, `OR`, `NOT`, `IN`). Pick
one. `{{service:checkout,env:prod}}` is right, and so is
`{{service:checkout AND env:prod}}`, but
`{{service:checkout,env:prod AND !region:eu}}`
is rejected outright. This is not the log query syntax, which does allow `AND`
and `OR` beside spaces — a metric query is a different grammar and the habit
does not carry over.

Not every metric supports every aggregator. A distribution metric answers
`avg:` or `p95:` only where that aggregation was configured for it, and asking
for one it does not have is rejected as a configuration error naming the
aggregation and the metric. That rejection is about the metric, not about the
service: try the metric's other aggregations, or another metric, and
never report the service as healthy on the strength of a query that was
refused.

Always scope the query to the service you were told about, and ask about the
window you were given rather than a period of your own choosing.
""".strip()
"""What a specialist writing a metric query needs to know, and nothing else."""
