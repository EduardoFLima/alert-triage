from datetime import UTC, datetime, timedelta

from alert_triage.adapters.adk.evidence import Retrieved, findings_from
from alert_triage.domain.findings import MAX_EXAMPLES_PER_FINDING, LogRecord, Signal

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _record(offset: timedelta = timedelta(), message: str = "OOMKilled") -> LogRecord:
    return LogRecord(
        timestamp=NOON + offset, level="ERROR", message=message, service="checkout"
    )


def _cited(
    cites: list[str], observation: str = "OOMKilled recurs", occurrences: int = 5
) -> dict[str, object]:
    return {"observation": observation, "occurrences": occurrences, "cites": cites}


def test_a_retrieved_record_is_offered_to_the_model_under_an_identifier() -> None:
    retrieved = Retrieved()

    (offered,) = retrieved.offer([_record(message="container OOMKilled")])

    assert offered["id"]
    assert offered["message"] == "container OOMKilled"


def test_two_searches_in_one_investigation_both_contribute() -> None:
    retrieved = Retrieved()

    first = retrieved.offer([_record(message="first")])
    second = retrieved.offer([_record(message="second")])

    first_record = retrieved.resolve(first[0]["id"])
    second_record = retrieved.resolve(second[0]["id"])
    assert first_record is not None and first_record.message == "first"
    assert second_record is not None and second_record.message == "second"


def test_identifiers_do_not_collide_across_searches() -> None:
    retrieved = Retrieved()

    first = retrieved.offer([_record(message="a"), _record(message="b")])
    second = retrieved.offer([_record(message="c")])

    identifiers = [offered["id"] for offered in (*first, *second)]
    assert len(set(identifiers)) == 3


def test_a_citation_to_a_record_that_was_never_retrieved_resolves_to_nothing() -> None:
    retrieved = Retrieved()
    retrieved.offer([_record()])

    assert retrieved.resolve("rec_never") is None


def test_findings_are_built_from_the_records_that_were_actually_returned() -> None:
    retrieved = Retrieved()
    (offered,) = retrieved.offer([_record(message="container OOMKilled")])

    (finding,) = findings_from([_cited([offered["id"]])], retrieved).findings

    assert finding.signal is Signal.LOGS
    assert finding.observation == "OOMKilled recurs"
    assert finding.occurrences == 5
    assert finding.examples == (_record(message="container OOMKilled"),)


def test_a_finding_citing_a_fabricated_record_is_dropped() -> None:
    """The model cannot write a log line, only cite one; an invented cite dies here."""
    retrieved = Retrieved()
    retrieved.offer([_record()])

    findings = findings_from([_cited(["rec_invented"])], retrieved)

    assert findings.findings == ()


def test_a_fabricated_finding_does_not_take_its_siblings_with_it() -> None:
    retrieved = Retrieved()
    (real,) = retrieved.offer([_record(message="real")])

    findings = findings_from(
        [
            _cited([real["id"]], observation="this one checks out"),
            _cited(["rec_invented"], observation="this one does not"),
        ],
        retrieved,
    )

    assert [finding.observation for finding in findings.findings] == [
        "this one checks out"
    ]


def test_a_finding_keeps_only_the_citations_that_resolve() -> None:
    retrieved = Retrieved()
    (real,) = retrieved.offer([_record(message="real")])

    (finding,) = findings_from(
        [_cited([real["id"], "rec_invented"])], retrieved
    ).findings

    assert finding.examples == (_record(message="real"),)


def test_a_payload_of_nothing_but_fabrications_is_empty_findings_not_an_error() -> None:
    """The investigation did run; it just said nothing that survived checking."""
    retrieved = Retrieved()
    retrieved.offer([_record()])

    findings = findings_from([_cited(["rec_a"]), _cited(["rec_b"])], retrieved)

    assert findings.findings == ()
    assert not findings.anything_notable


def test_a_finding_citing_nothing_at_all_is_dropped() -> None:
    retrieved = Retrieved()
    retrieved.offer([_record()])

    assert findings_from([_cited([])], retrieved).findings == ()


def test_an_occurrence_count_below_the_surviving_citations_is_raised_to_fit() -> None:
    """A count the model got wrong must not make a good finding unbuildable."""
    retrieved = Retrieved()
    offered = retrieved.offer([_record(message="a"), _record(message="b")])

    (finding,) = findings_from(
        [_cited([one["id"] for one in offered], occurrences=1)], retrieved
    ).findings

    assert finding.occurrences == 2


def test_more_citations_than_a_finding_shows_are_capped() -> None:
    retrieved = Retrieved()
    offered = retrieved.offer(
        [_record(timedelta(seconds=n)) for n in range(MAX_EXAMPLES_PER_FINDING + 5)]
    )

    (finding,) = findings_from(
        [_cited([one["id"] for one in offered], occurrences=400)], retrieved
    ).findings

    assert len(finding.examples) == MAX_EXAMPLES_PER_FINDING
    assert finding.occurrences == 400


def test_an_observation_with_nothing_to_say_is_dropped() -> None:
    retrieved = Retrieved()
    (offered,) = retrieved.offer([_record()])

    assert (
        findings_from([_cited([offered["id"]], observation="  ")], retrieved).findings
        == ()
    )
