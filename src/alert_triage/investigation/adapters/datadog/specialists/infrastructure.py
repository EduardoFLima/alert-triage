"""The infrastructure specialist, declared: its tools, its instruction, and its schema.

Resource pressure comes from metrics and hosts on ``core``; the workload the
service runs as comes from ``kubernetes``, where the deployment has one. The
second toolset is the reason this specialist is the one that forced the empty
answer to stop counting as a failure: a service on virtual machines has no
container workload, and the platform says so by answering that there are none.

That answer is a fact about the deployment. It is told to the model here in as
many words, because a model asked to find a workload that does not exist will
otherwise keep asking for it, or report its absence as something wrong with the
service. The system draws the same distinction on the way in, where an empty
answer is retained as a retrieval that found nothing.
"""

from pydantic import BaseModel, Field

from alert_triage.investigation.adapters.datadog.specialists.dialect import (
    CONSULT_THE_PLATFORM,
    METRIC_QUERY_DIALECT,
    SKILL_LIST_TOOL,
    SKILL_LOAD_TOOL,
)
from alert_triage.investigation.contract import MAX_EXAMPLES_PER_FINDING, Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset

CORE_TOOLSET = "core"
KUBERNETES_TOOLSET = "kubernetes"
"""The toolsets on the platform's server holding what this specialist reaches.

Both are asked for separately rather than as one connection: the group is how
the platform organises its tools, and a specialist declaring which group it
reaches for what is a specialist whose live check says which half is missing.
"""

METRIC_TOOL = "get_datadog_metric"
METRIC_SEARCH_TOOL = "search_datadog_metrics"
METRIC_CONTEXT_TOOL = "get_datadog_metric_context"
HOSTS_TOOL = "search_datadog_hosts"
K8S_SEARCH_TOOL = "search_datadog_k8s_resources"
K8S_DESCRIBE_TOOL = "describe_datadog_k8s_resource"
"""The tools this specialist may reach, and the only ones."""

INFRASTRUCTURE_INSTRUCTION = f"""
You are an infrastructure specialist doing the first-pass investigation a
knowledgeable engineer would do for a service that has started alerting.

You will be told a service and the window its alerts span. Report what the
service runs on and what its resources were doing over that window: CPU,
memory, disk and network — what was saturated, how far it went, and when it
began relative to the alerts.

The tools you have are Datadog's:

- `{METRIC_SEARCH_TOOL}` lists the metrics that exist, filtered by name or by
  tag — `service:the-service` is how you narrow it to one service's, and a
  host tag is how you narrow it to one host's.
- `{METRIC_CONTEXT_TOOL}` takes one metric you have already found and tells
  you its unit, its type and what tags it carries.
- `{METRIC_TOOL}` returns a metric's values over a time range.
- `{HOSTS_TOOL}` finds the hosts a service runs on, with the tags that say
  what they are.
- `{K8S_SEARCH_TOOL}` finds the container workloads a service runs as, where
  the deployment has them.
- `{K8S_DESCRIBE_TOOL}` returns one such workload in full, including its
  restarts and why it was last rescheduled.

{CONSULT_THE_PLATFORM}

Ask `{METRIC_SEARCH_TOOL}` which metrics are reported before you query one,
and read the name you query out of what it answers. Do not guess a metric
name: a name nothing reports comes back empty, and an empty answer means it is
not reported, which is not the same as the resource being healthy. A managed
service reports a different set from a virtual machine, and neither reports
everything.

{METRIC_QUERY_DIALECT}

Prefer `max:` over `avg:` where a single saturated host matters more than the
average across them, which for resource pressure is usually the case: one host
out of memory is an incident that an average over ten hosts hides.

What to report:

- The resource pressure you found, naming the resource, how far it went, and
  when it began relative to the alerts. If the resources were unremarkable
  through the window, say so — that is a useful answer.
- The state of the workload the service runs as, where the platform has one,
  including restarts and scheduling failures over the window.

Rules you must follow:

- If the platform answers that there are none — no container workload, no
  hosts, no such metric — that is the deployment telling you it does not have
  that signal. It is an answer, not a failure, and not a failure to report or
  work around. Say what the deployment does have and move on. Do not keep
  asking for a workload that does not exist, and do not report its absence as
  something wrong with the service.
- If a retrieval comes back saying it failed, that is a different thing
  entirely: it means the retrieval did not run. It does not mean the resources
  were healthy, and you must not conclude anything at all about them from it.
  Try another retrieval, and report only what the retrievals that succeeded
  show.
- Every result you are given back is identified. A retrieval is `call-N`, and
  each individual entry within it is `call-N/item-M`. Cite what shows your
  observation: `call-N/item-M` for individual hosts, workloads or points, and
  `call-N` for an aggregate, where there are no individual entries to point
  at. Cite at most {MAX_EXAMPLES_PER_FINDING} per observation, choosing ones
  that represent what you observed. An observation citing neither will be
  discarded.
- Never write out a metric value, a host or a workload yourself. You cite what
  you were shown; you do not compose it. An observation citing something you
  were not shown will be discarded.
- Do not name a root cause, offer a hypothesis, state a confidence level, or
  recommend an action. Another agent reasons across signals and concludes;
  your job is to say accurately what the infrastructure shows.
""".strip()


class InfrastructureFinding(BaseModel):
    """One thing the agent observed underneath the service, with what it rests on."""

    observation: str = Field(
        description=(
            "What was observed: the resource or the workload, how far it went, "
            "and when it began relative to the alerts."
        )
    )
    occurrences: int = Field(
        description="How many retrieved hosts, workloads or points show it.", ge=0
    )
    cites: list[str] = Field(
        description=(
            "What shows this observation, by the identifiers you were given: "
            "`call-N/item-M` for individual entries, `call-N` for an aggregate. "
            f"At most {MAX_EXAMPLES_PER_FINDING} of them."
        )
    )


class ReportedFindings(BaseModel):
    """Everything the agent has to report about what one incident's service runs on."""

    findings: list[InfrastructureFinding] = Field(
        default_factory=list,
        description=(
            "What was observed. Empty when the infrastructure was unremarkable, "
            "or when the deployment does not carry this signal."
        ),
    )


INFRASTRUCTURE_SPECIALIST = Specialist(
    name="infrastructure_specialist",
    signal=Signal.INFRASTRUCTURE,
    instruction=INFRASTRUCTURE_INSTRUCTION,
    output_schema=ReportedFindings,
    toolsets=(
        Toolset(
            name=CORE_TOOLSET,
            tools=(
                METRIC_TOOL,
                METRIC_SEARCH_TOOL,
                METRIC_CONTEXT_TOOL,
                HOSTS_TOOL,
                SKILL_LIST_TOOL,
                SKILL_LOAD_TOOL,
            ),
        ),
        Toolset(name=KUBERNETES_TOOLSET, tools=(K8S_SEARCH_TOOL, K8S_DESCRIBE_TOOL)),
    ),
)
"""The infrastructure specialist as the crew sees it: one declaration, nothing else."""
