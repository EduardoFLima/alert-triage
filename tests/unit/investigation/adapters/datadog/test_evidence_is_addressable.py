"""Where a reader goes to see for themselves what a retrieval returned.

An address is derived from the payload and the arguments the tool was called
with, never from what a specialist wrote. Both grains are covered: an item the
payload identifies, and the retrieval it came from, which is the fallback for an
item the payload does not identify.
"""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from alert_triage.investigation.adapters.datadog.links import DatadogLinks

LOG_SEARCH = "search_datadog_logs"
"""Every address here is a log search; which product a tool opens is its own test."""

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
ONE_PM = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)

SEARCH = {
    "query": "service:checkout status:error",
    "from": NOON.isoformat(),
    "to": ONE_PM.isoformat(),
}


def _links(web_host: str = "app.datadoghq.com") -> DatadogLinks:
    return DatadogLinks(web_host)


def test_an_organisation_on_its_own_subdomain_is_addressed_there() -> None:
    """``app`` is where most accounts live, not where every account lives."""
    address = _links("foobar.datadoghq.eu").to_retrieval(SEARCH, tool=LOG_SEARCH)

    assert address is not None
    assert urlparse(address).netloc == "foobar.datadoghq.eu"


def _parameters(address: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(address).query)


def test_a_payload_naming_an_item_is_addressed_as_that_item() -> None:
    retrieval = _links().to_retrieval(SEARCH, tool=LOG_SEARCH)

    address = _links().to_item(
        {"id": "AQAAA-log-1", "message": "OOMKilled"}, retrieval, tool=LOG_SEARCH
    )

    assert address is not None
    assert _parameters(address)["event"] == ["AQAAA-log-1"]


def test_an_items_address_still_carries_the_search_that_produced_it() -> None:
    """An address that degrades to the right search never leads nowhere."""
    retrieval = _links().to_retrieval(SEARCH, tool=LOG_SEARCH)

    address = _links().to_item({"id": "AQAAA-log-1"}, retrieval, tool=LOG_SEARCH)

    assert address is not None
    assert _parameters(address)["query"] == ["service:checkout status:error"]


def test_a_payload_naming_no_item_is_addressed_as_its_retrieval() -> None:
    """A reader lands on the search that produced it rather than nowhere."""
    retrieval = _links().to_retrieval(SEARCH, tool=LOG_SEARCH)

    assert (
        _links().to_item({"message": "OOMKilled"}, retrieval, tool=LOG_SEARCH)
        == retrieval
    )


def test_a_payload_nothing_can_be_read_out_of_has_no_address() -> None:
    assert _links().to_item("the service looks fine", None, tool=LOG_SEARCH) is None


def test_a_retrievals_address_carries_the_query_it_was_called_with() -> None:
    address = _links().to_retrieval(SEARCH, tool=LOG_SEARCH)

    assert address is not None
    assert address.startswith("https://app.datadoghq.com/logs?")
    assert _parameters(address)["query"] == ["service:checkout status:error"]


def test_a_query_is_encoded_rather_than_pasted_into_the_address() -> None:
    """A raw space or colon in a URL is what makes a link stop opening."""
    address = _links().to_retrieval(
        {"query": "service:checkout status:error"}, tool=LOG_SEARCH
    )

    assert address is not None
    assert " " not in address


def test_a_retrievals_address_carries_the_window_it_ran_over() -> None:
    address = _links().to_retrieval(SEARCH, tool=LOG_SEARCH)

    assert address is not None
    assert _parameters(address)["from_ts"] == [str(int(NOON.timestamp() * 1000))]
    assert _parameters(address)["to_ts"] == [str(int(ONE_PM.timestamp() * 1000))]


def test_the_window_is_pinned_so_the_address_outlives_the_moment() -> None:
    """A live view days later shows the present, which is not the evidence."""
    address = _links().to_retrieval(SEARCH, tool=LOG_SEARCH)

    assert address is not None
    assert _parameters(address)["live"] == ["false"]


def test_a_window_given_in_epoch_milliseconds_is_read_as_it_was_meant() -> None:
    """The tool takes what the model gives it, which is not always an instant."""
    address = _links().to_retrieval(
        {
            "query": "service:checkout",
            "from": int(NOON.timestamp() * 1000),
            "to": int(ONE_PM.timestamp() * 1000),
        },
        tool=LOG_SEARCH,
    )

    assert address is not None
    assert _parameters(address)["from_ts"] == [str(int(NOON.timestamp() * 1000))]


def test_a_window_nothing_can_be_made_of_is_left_off_rather_than_invented() -> None:
    """A wrong window is a link to the wrong evidence, which is worse than none."""
    address = _links().to_retrieval(
        {"query": "service:checkout", "from": "the day before"}, tool=LOG_SEARCH
    )

    assert address is not None
    assert "from_ts" not in _parameters(address)
    assert _parameters(address)["query"] == ["service:checkout"]


def test_a_retrieval_with_no_query_is_still_addressed() -> None:
    """A tool called with something this adapter cannot read is still evidence."""
    address = _links().to_retrieval({}, tool=LOG_SEARCH)

    assert address is not None
    assert address.startswith("https://app.datadoghq.com/logs?")


def test_an_account_on_another_site_never_receives_a_com_address() -> None:
    retrieval = _links("app.datadoghq.eu").to_retrieval(SEARCH, tool=LOG_SEARCH)
    item = _links("app.datadoghq.eu").to_item(
        {"id": "log-1"}, retrieval, tool=LOG_SEARCH
    )

    assert retrieval is not None and item is not None
    assert urlparse(retrieval).netloc == "app.datadoghq.eu"
    assert urlparse(item).netloc == "app.datadoghq.eu"
