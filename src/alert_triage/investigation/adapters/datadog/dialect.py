"""Metric grammar is shared because Datadog rejects log-query habits here."""

AN_EMPTY_ANSWER = """
An empty answer is about what you asked, not about the service. It means what
you asked for is not reported, which is not the same as healthy: a query naming
something the service does not carry comes back empty exactly as a quiet one
does, and the two readings are opposite findings. Before you report that
something was quiet, be sure what you asked about is something the service
reports.
""".strip()
"""Shared principle; each specialist decides how to check whether a name exists."""

IN_THE_ENVIRONMENT = """
Scope every query to the service you were told about and to the environment you
were told about, with the `env` tag beside the service: the same service runs in
more than one environment, and evidence drawn from another is not evidence
about this incident. Where you were told no environment, scope by the service
alone.
""".strip()
"""Instruction rather than rewrite, so the run still shows what was asked."""

_METRIC_QUERY_GRAMMAR = """
A metric query is an aggregator, a metric name, and a scope in braces:
`avg:system.cpu.user{service:checkout}`. Use `sum:...{service:checkout}.as_count()`
for a count, and `p95:` where an average would hide the tail.

Inside the braces, separate tags with commas, and a comma means AND:
`{service:checkout,env:prod}`. Prefix a tag with `!` to exclude it.

Do not write `AND`, `OR`, `NOT` or `IN` in the same braces as a comma or a `!`.
Datadog has two filter grammars and rejects a query that mixes them: the
symbolic one (`,` and `!`) and the worded one (`AND`, `OR`, `NOT`, `IN`). Pick
one. `{service:checkout,env:prod}` is right, and so is
`{service:checkout AND env:prod}`, but `{service:checkout,env:prod AND !region:eu}`
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
""".strip()

METRIC_QUERY_DIALECT = f"""{_METRIC_QUERY_GRAMMAR}

{IN_THE_ENVIRONMENT} Ask about the window you were given rather than a period
of your own choosing."""
