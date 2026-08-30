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

SKILL_LIST_TOOL = "list_datadog_skills"
SKILL_LOAD_TOOL = "load_datadog_skill"
"""How the platform publishes the grammars its own tools are queried in.

Named here rather than in each specialist because every specialist that
queries anything reaches both, and because this is the module that exists to
answer "how is a query written on this platform" — which these two answer
better than a transcription can.
"""

CONSULT_THE_PLATFORM = f"""
This platform documents how its own tools are queried, and that documentation
is the authority on syntax — not your recollection of it, and not the shape of
a query you wrote for a different tool.

- `{SKILL_LIST_TOOL}` lists the guides it publishes.
- `{SKILL_LOAD_TOOL}` loads one, by the name the listing gave it. A guide may
  point you at a further reference of its own; load that one the same way,
  passing the path it named you.

Load the guide covering a tool before you write your first query with it. The
tools here take several different query languages — one takes SQL over a
virtual table, another a tag filter, another a metric expression — and they
look enough alike that a query written in the wrong one is accepted by you and
refused by the platform. A refusal costs a retrieval; loading a guide costs a
call.
""".strip()
"""Where a specialist is told to find the grammar rather than be given it.

Shared by every specialist that queries anything, which is all of them. What
each one then loads is the model's to decide from the listing: naming a guide
here would be the transcription this replaced, one indirection out, and stale
the day the platform renames it.
"""

METRIC_QUERY_DIALECT = """
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

Always scope the query to the service you were told about, and ask about the
window you were given rather than a period of your own choosing.
""".strip()
"""What a specialist writing a metric query needs to know, and nothing else."""
