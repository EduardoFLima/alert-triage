"""Reading discrete, citable items out of whatever a tool happened to return.

No per-tool knowledge: a result is a list, a list in an envelope, or one thing,
and the third degrades to something citable whole rather than to an error.
"""

from datetime import UTC, datetime

from alert_triage.investigation.adapters.adk.normalisation import items_from

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def test_a_bare_list_of_entries_becomes_one_item_each_in_order() -> None:
    items = items_from(
        [{"message": "first"}, {"message": "second"}, {"message": "third"}], "call-1"
    )

    assert [item.summary for item in items] == ["first", "second", "third"]
    assert [item.id for item in items] == [
        "call-1/item-1",
        "call-1/item-2",
        "call-1/item-3",
    ]


def test_entries_wrapped_in_a_recognised_envelope_are_found() -> None:
    items = items_from(
        {"logs": [{"message": "first"}, {"message": "second"}]}, "call-2"
    )

    assert [item.summary for item in items] == ["first", "second"]


def test_the_envelope_is_not_itself_an_item() -> None:
    """Two items from a wrapped pair, not three: the wrapper evidences nothing."""
    items = items_from(
        {"data": [{"message": "first"}, {"message": "second"}]}, "call-1"
    )

    assert len(items) == 2


def test_a_result_with_no_readable_items_yields_none_rather_than_an_error() -> None:
    """A tool nobody anticipated degrades to a citable aggregate."""
    assert items_from({"flame_graph": {"root": {"self_time_ms": 42}}}, "call-1") == ()


def test_an_item_reads_the_instant_the_payload_offers() -> None:
    (item,) = items_from(
        [{"timestamp": NOON.isoformat(), "message": "OOMKilled"}], "call-1"
    )

    assert item.instant == NOON


def test_an_item_whose_payload_offers_no_instant_has_none() -> None:
    (item,) = items_from([{"message": "OOMKilled"}], "call-1")

    assert item.instant is None


def test_an_unreadable_timestamp_is_no_instant_rather_than_an_error() -> None:
    (item,) = items_from(
        [{"timestamp": "the day before", "message": "OOMKilled"}], "call-1"
    )

    assert item.instant is None
    assert item.summary == "OOMKilled"


def test_an_item_keeps_the_payload_verbatim() -> None:
    payload = {"message": "OOMKilled", "attributes": {"pod": "checkout-7f"}}

    (item,) = items_from([payload], "call-1")

    assert item.payload == payload


def test_an_item_with_no_obvious_line_is_summarised_from_its_payload() -> None:
    (item,) = items_from([{"pod": "checkout-7f", "restarts": 4}], "call-1")

    assert "checkout-7f" in item.summary
    assert "restarts" in item.summary


def test_an_entry_that_is_not_a_record_is_still_an_item() -> None:
    (item,) = items_from(["something the platform said"], "call-1")

    assert item.summary == "something the platform said"


def test_a_long_summary_is_shortened_to_stay_readable() -> None:
    (item,) = items_from([{"message": "x" * 5000}], "call-1")

    assert len(item.summary) < 5000


def test_shortening_never_cuts_a_word_in_half() -> None:
    """A half a URL is worse than no URL: it reads as a link and is not one."""
    link = "https://app.datadoghq.com/logs?query=" + "a" * 200
    (item,) = items_from([{"message": f"{'padding ' * 20}{link}"}], "call-1")

    assert link not in item.summary
    assert "https://app.datadoghq.com/logs?query=a" not in item.summary


def test_a_shortened_summary_ends_clear_of_its_last_word() -> None:
    """Whitespace is what stops a client linkifying the ellipsis into the URL."""
    (item,) = items_from([{"message": "word " * 200}], "call-1")

    assert item.summary.endswith(" …")


def test_a_single_word_too_long_to_keep_is_still_shortened() -> None:
    """There is no word boundary to fall back to, and a summary cannot be empty."""
    (item,) = items_from([{"message": "x" * 5000}], "call-1")

    assert item.summary.strip("… ")
    assert len(item.summary) < 5000


def test_entries_are_found_inside_a_structured_tool_result() -> None:
    """The protocol's own wrapping is not evidence either."""
    items = items_from(
        {"structuredContent": {"logs": [{"message": "first"}]}, "isError": False},
        "call-1",
    )

    assert [item.summary for item in items] == ["first"]


def test_entries_are_found_inside_a_tool_result_answered_as_text() -> None:
    items = items_from(
        {"content": [{"type": "text", "text": '[{"message": "first"}]'}]}, "call-1"
    )

    assert [item.summary for item in items] == ["first"]


def test_a_tool_result_that_is_prose_has_no_items() -> None:
    result = {"content": [{"type": "text", "text": "the service looks fine"}]}

    assert items_from(result, "call-1") == ()


def test_entries_are_found_under_the_protocols_own_wrapper() -> None:
    """A tool answering with a list has it wrapped, because content is an object."""
    items = items_from(
        {"structuredContent": {"result": [{"message": "first"}]}}, "call-1"
    )

    assert [item.summary for item in items] == ["first"]
