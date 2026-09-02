"""What was asked is a fact of its own, kept apart from what was retrieved.

A specialist nobody consulted and a specialist that looked and found nothing are
opposite pieces of news, and only a record of what was asked can tell them
apart. ``Retrieved`` cannot: it holds evidence, and a consultation that gathered
none looks exactly like a consultation that never happened.
"""

from typing import Any

from pydantic import BaseModel

from alert_triage.investigation.adapters.adk.consultation import Consulted
from alert_triage.investigation.adapters.adk.evidence import Retrieved
from alert_triage.investigation.contract import Signal
from alert_triage.investigation.domain.specialist import Specialist, Toolset


class _Reported(BaseModel):
    findings: list[dict[str, Any]] = []


LOGS = Specialist(
    name="logs_specialist",
    signal=Signal.LOGS,
    instruction="Look at the logs.",
    output_schema=_Reported,
    toolsets=(Toolset(name="core", tools=("search_datadog_logs",)),),
)
APM = Specialist(
    name="apm_specialist",
    signal=Signal.APM,
    instruction="Look at the golden signals.",
    output_schema=_Reported,
    toolsets=(Toolset(name="core", tools=("get_datadog_metric",)),),
)


def _report(*cites: str, observation: str = "OOMKilled recurs") -> dict[str, Any]:
    return {
        "findings": [
            {"observation": observation, "occurrences": 3, "cites": list(cites)}
        ]
    }


def _consulted(*crew: Specialist) -> tuple[Consulted, Retrieved]:
    retrieved = Retrieved()
    return Consulted(offered=crew, retrieved=retrieved), retrieved


def test_it_knows_the_whole_crew_it_offered() -> None:
    consulted, _ = _consulted(LOGS, APM)

    assert consulted.offered == (LOGS, APM)


def test_it_records_which_specialists_were_asked_in_order() -> None:
    consulted, retrieved = _consulted(LOGS, APM)
    retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})

    consulted.record(APM, _report("call-1"))
    consulted.record(LOGS, _report("call-1"))

    assert consulted.order == ("apm_specialist", "logs_specialist")


def test_it_accumulates_the_findings_that_survived() -> None:
    consulted, retrieved = _consulted(LOGS, APM)
    retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})

    consulted.record(LOGS, _report("call-1/item-1", observation="the logs recur"))
    consulted.record(APM, _report("call-1", observation="latency doubled"))

    assert [finding.observation for finding in consulted.findings] == [
        "the logs recur",
        "latency doubled",
    ]
    assert [finding.signal for finding in consulted.findings] == [
        Signal.LOGS,
        Signal.APM,
    ]


def test_the_signals_consulted_name_each_one_once() -> None:
    """A specialist asked twice consulted one signal, and cost two questions."""
    consulted, retrieved = _consulted(LOGS, APM)
    retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})

    consulted.record(LOGS, _report("call-1/item-1"))
    consulted.record(LOGS, _report("call-1/item-1"))

    assert consulted.signals == (Signal.LOGS,)
    assert consulted.order == ("logs_specialist", "logs_specialist")


def test_a_specialist_never_asked_names_no_signal() -> None:
    consulted, retrieved = _consulted(LOGS, APM)
    retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})

    consulted.record(LOGS, _report("call-1/item-1"))

    assert consulted.signals == (Signal.LOGS,)
    assert Signal.APM not in consulted.signals


def test_a_specialist_whose_findings_were_all_discarded_was_still_consulted() -> None:
    """Consultation and evidence are independent facts, and this is where they part."""
    consulted, retrieved = _consulted(LOGS)
    retrieved.retain_evidence({"logs": [{"message": "OOMKilled"}]})

    consulted.record(LOGS, _report("call-9/item-1"))

    assert consulted.findings == ()
    assert consulted.signals == (Signal.LOGS,)


def test_a_tool_name_that_is_not_a_specialist_resolves_to_nothing() -> None:
    consulted, _ = _consulted(LOGS)

    assert consulted.named("logs_specialist") is LOGS
    assert consulted.named("set_model_response") is None
