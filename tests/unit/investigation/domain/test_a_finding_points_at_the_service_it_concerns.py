"""Each finding carries where to go and look at the service, beside its evidence.

Two addresses with two jobs: an evidence item's says where that evidence came
from, and a finding's says where to look at the service it concerns, opened on
the section it named. The account renders both and composes neither — how a
platform addresses a service page is an adapter's knowledge, handed in.
"""

from datetime import UTC, datetime

from alert_triage.investigation.contract import (
    EvidenceItem,
    Finding,
    Findings,
    Section,
    Signal,
)
from alert_triage.investigation.domain.account import (
    SERVICE_PAGE_LABEL,
    compose,
    without_words,
)

NOON = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
LOG_LINK = "https://platform/logs?query=service%3Acheckout"


def _page(finding: Finding) -> str | None:
    """A platform's service page, anchored to whatever section the finding named."""
    anchor = "" if finding.section is None else f"#{finding.section.value}"
    return f"https://platform/service/checkout{anchor}"


def _findings(section: Section | None = None) -> Findings:
    item = EvidenceItem(
        id="call-1", instant=NOON, summary="rolled out", payload={}, url=LOG_LINK
    )
    return Findings(
        findings=(
            Finding(
                signal=Signal.INFRASTRUCTURE,
                observation="checkout was rolled out",
                occurrences=1,
                examples=(item,),
                section=section,
            ),
        )
    )


def _lines(account: str) -> list[str]:
    return [line.strip() for line in account.splitlines()]


def test_a_finding_with_a_section_points_at_that_section_of_the_service() -> None:
    lines = _lines(compose("Narrative.", _findings(Section.INFRASTRUCTURE), page=_page))

    finding = lines.index("- [infrastructure] checkout was rolled out (seen 1 time)")
    assert lines[finding + 1] == (
        f"{SERVICE_PAGE_LABEL} https://platform/service/checkout#infrastructure"
    )


def test_a_finding_with_no_section_points_at_the_service_as_a_whole() -> None:
    account = compose("Narrative.", _findings(), page=_page)

    assert f"{SERVICE_PAGE_LABEL} https://platform/service/checkout" in account
    assert "#" not in account


def test_the_evidences_own_address_is_still_rendered_beside_it() -> None:
    """Where the evidence came from is not replaced by where to look at the service."""
    lines = _lines(compose("Narrative.", _findings(Section.INFRASTRUCTURE), page=_page))

    assert LOG_LINK in lines


def test_a_finding_the_platform_offers_no_page_for_points_nowhere() -> None:
    account = compose("Narrative.", _findings(), page=lambda finding: None)

    assert SERVICE_PAGE_LABEL not in account


def test_an_account_given_no_page_points_nowhere() -> None:
    """A deployment with no platform addresses renders findings as it always did."""
    assert SERVICE_PAGE_LABEL not in compose("Narrative.", _findings())


def test_an_unworded_account_points_at_the_service_too() -> None:
    account = without_words(None, None, _findings(Section.LOGS), page=_page)

    assert f"{SERVICE_PAGE_LABEL} https://platform/service/checkout#logs" in account
