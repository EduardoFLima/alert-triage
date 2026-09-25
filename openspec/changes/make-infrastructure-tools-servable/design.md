## Context

See proposal.md — Why.

The refusal comes from the model platform, not from Datadog: the MCP server
serves these tools happily, and the same schemas are accepted by other clients.
What the platform objects to is branching — a schema with enough unions,
optional objects and nested alternatives that it cannot compile a grammar for
serving. The Kubernetes tools' filter arguments are where that branching is.

The diagnosis has to come before the fix, because two remedies are available
and which one is right depends on whether the branching is in one tool or in
all of them.

## Goals / Non-Goals

**Goals:** the infrastructure specialist reaching the model; a refused tool
costing its own signal rather than the whole consultation; a live check that
names a specialist which cannot be served.

**Non-Goals:** changing what the specialist reports. Changing the Datadog MCP
server. Making the system resilient to model-platform failures in general —
this is about one refusal, given before anything runs.

## Decisions

**Establish which tool is refused before deciding how to fix it.** Offer each
of the specialist's tools alone against the real platform and record which are
served. The alternative — assuming the Kubernetes toolset as a whole and
dropping it — would lose workload state and rollouts, which the spec requires,
on a guess.

**Prefer simplifying the declared schema to dropping the tool.** A tool is
declared here with the arguments the specialist is allowed to pass, and a
specialist rarely needs the full generality of a platform's filter grammar.
Narrowing what is declared removes branching without removing the tool. The
alternative — dropping the refused tool — is the fallback where narrowing does
not bring it under the platform's limit.

**A refusal is caught at the boundary and reported as an absent signal.** The
project already distinguishes an empty answer from a failed retrieval, and
already treats a toolset the deployment has not configured as the former. A
platform refusing a tool is the same kind of fact and gets the same treatment.
The alternative — letting it fail the consultation — is the current behaviour
and the defect.

**The live check asserts every specialist can be served, not just that one
can.** The existing check exercises a specialist that reaches the model; the
failure here was that nobody asked the same of the rest. A check that only
covers the specialists already known to work is a check that cannot find this
class of defect again.

## Risks / Trade-offs

**A narrowed schema may refuse a query the specialist would have wanted.** The
trade is a tool that runs with fewer options against a tool that does not run.
Mitigated by narrowing to what the instruction actually tells the model to ask
for, which is a search by cluster, namespace and name.

**Narrowing may not be enough.** The platform's limit is not documented as a
number, so the only way to know is to try. Mitigated by the fallback of
dropping the tool, and by the spec treating its signal as empty rather than
failed.

**Swallowing a refusal could hide a real misconfiguration.** A tool refused for
a reason that is not a schema — a wrong model, a revoked permission — would be
reported as an absent signal. Mitigated by the live check, which fails on a
specialist that cannot be served at all rather than reporting it empty.
