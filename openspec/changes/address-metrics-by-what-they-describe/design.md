## Context

See proposal.md — Why.

`DatadogLinks` routes on the tool alone, and `APM_SERVICE_TOOLS` puts the three
metric tools on the same template as the service catalogue. The file's own
docstring already states the principle this violates: an address is what the
retrieval came from. A metric retrieval came from a metric.

The rule that only confirmed templates ship is the constraint that shapes the
work: every new template here is a guess until a live run opens it, and the
change has to be shaped so that a failed guess costs nothing but an absent
address.

## Goals / Non-Goals

**Goals:** each metric tool addressed at the view answering for what it
fetched; an unreadable subject yielding no address; every new template
confirmed live before it ships.

**Non-Goals:** widening addressing to the tools currently in `UNADDRESSED`.
Changing where the service catalogue points. Anything about the per-finding
service link.

## Decisions

**Route by what the tool fetches, not by which specialist called it.** The
alternative is to thread the specialist's signal into the linker and let an
infrastructure metric open an infrastructure page while an APM metric opens the
APM page. Rejected: it puts knowledge of the crew inside the platform adapter,
and it makes the same retrieval open two different views depending on who asked
— which is exactly the mismatch between address and subject being fixed. A
metric is a metric; the view that answers for it is the same either way.

**Three tools, three views.** A metric search matched names, so it opens the
summary of metrics matching that filter. A metric's context described one
metric, so it opens that metric's own summary. A metric query returned a
series, so it opens the explorer over that query and window. The alternative —
one metric view for all three — is simpler and wrong in two of the three cases:
a name search does not have a series to plot.

**The subject is read from the call's arguments, and absence is an answer.**
The metric name is what each of these three views is scoped by, and it is in
the arguments the model supplied. Where it is not readable, the tool falls back
to no address, the same way an unmapped tool does today. The alternative —
falling back to the service's APM page — is the current behaviour and the
defect.

**A template that does not open live is deleted and the tool moves to
`UNADDRESSED`.** The alternative is shipping it and noting the doubt in a
comment, which the previous change already rejected: a reader does not read
comments.

## Risks / Trade-offs

**Fewer addresses than before.** A metric retrieval whose name cannot be read
loses an address it used to have. That is the point — it was an address to the
wrong thing — but a report with visibly fewer links can read as a regression.
Mitigated by saying so in the change's record, and by the metric name being
present in the arguments of a well-formed call.

**The metric views may not accept the scoping assumed.** Mitigated by the live
confirmation gate: an unconfirmed template never ships.

**`_service_templates` grows a second axis of meaning** — tools that scope by
service and tools that scope by metric now sit in one map. Mitigated by naming
the groups for what they scope by rather than for which page they open.
