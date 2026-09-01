"""A run's account, shaped so a human finds the thing they came looking for.

Every rule here exists for a reader scrolling a terminal: a phase announces
itself unmistakably, what belongs to it is aligned beneath it, and nothing a
model said is silently cut short.
"""

from alert_triage.shared import journal


def test_a_phase_announces_itself_in_a_box() -> None:
    written = journal.banner("REPORTING", "checkout")

    assert "│ REPORTING · checkout" in written
    assert "╭─" in written
    assert "╰─" in written


def test_a_box_closes_on_the_line_it_opened() -> None:
    """A ragged right edge reads as a broken box rather than a heading."""
    written = journal.banner("REPORTING", "checkout")
    lines = [line for line in written.splitlines() if line]

    assert len({len(line) for line in lines}) == 1


def test_a_box_widens_rather_than_breaking_around_a_long_subject() -> None:
    written = journal.banner("INCIDENT", "a-service-with-a-very-long-name" * 3)
    lines = [line for line in written.splitlines() if line]

    assert len({len(line) for line in lines}) == 1
    assert "a-service-with-a-very-long-name" in written


def test_a_phase_with_nothing_to_qualify_it_is_named_alone() -> None:
    assert "│ RUN COMPLETE" in journal.banner("RUN COMPLETE")


def test_what_belongs_to_a_phase_is_aligned_beneath_it() -> None:
    written = journal.banner("INCIDENT", "checkout", alerts=4, attempt="1 of 3")

    alerts, attempt = (
        line for line in written.splitlines() if "alerts" in line or "attempt" in line
    )
    assert alerts.index("4") == attempt.index("1 of 3")


def test_a_detail_names_itself_in_words_rather_than_in_code() -> None:
    assert "alert count" in journal.banner("INCIDENT", "checkout", alert_count=4)


def test_a_detail_nobody_could_state_is_left_out() -> None:
    """An optional the run does not have is absent, not an empty row."""
    written = journal.banner("INCIDENT", "checkout", hypothesis=None, alerts=4)

    assert "hypothesis" not in written
    assert "alerts" in written


def test_a_smaller_moment_is_captioned_rather_than_boxed() -> None:
    written = journal.event("consulting logs_specialist", request="what changed?")

    assert "── consulting logs_specialist ─" in written
    assert "╭" not in written
    assert "what changed?" in written


def test_what_an_agent_said_is_written_under_its_caption() -> None:
    written = journal.event("diagnostician reasoning", "I will ask the logs first.")

    assert "  I will ask the logs first." in written


def test_a_long_value_wraps_under_itself_rather_than_running_on() -> None:
    written = journal.banner("CONCLUDED", "checkout", hypothesis="a leak. " * 12)
    first, second = (line for line in written.splitlines() if "leak" in line)

    assert len(first) <= journal.WIDTH
    assert len(second) - len(second.lstrip()) == first.index("a leak")


def test_a_long_observation_is_given_its_own_lines_and_kept_whole() -> None:
    """What a specialist observed is the thing a human came to read."""
    observed = "The pods are OOM-killed. " * 20
    written = journal.event("logs_specialist reported", observation=observed)

    said = " ".join(written.split())
    assert observed.strip() in said
    assert written.splitlines()[2].strip() == "observation"


def test_what_was_said_in_paragraphs_is_read_in_paragraphs() -> None:
    written = journal.event("reported", observation="First thing.\n\nSecond thing.")
    body = [line.strip() for line in written.splitlines()]

    assert body.index("First thing.") + 2 == body.index("Second thing.")


def test_a_block_opens_on_a_line_of_its_own() -> None:
    """It sits under the timestamp and level, never beside them.

    The blank line *below* a block is not its business: every record is followed
    by one, which is the only way a stack trace gets the same courtesy.
    """
    written = journal.banner("REPORTING", "checkout")

    assert written.startswith("\n")
    assert not written.endswith("\n")


def test_a_block_ends_once_rather_than_trailing_off() -> None:
    """One blank line separates blocks; two read as something having gone wrong."""
    assert not journal.event("diagnostician reasoning", "One thought.").endswith("\n\n")


def test_something_too_long_to_read_is_shortened_and_says_how_much_it_dropped() -> None:
    shortened = journal.shortened("x" * 900, limit=100)

    assert shortened.startswith("x" * 90)
    assert len(shortened) < 200
    assert "800 more" in shortened


def test_something_short_enough_to_read_is_left_exactly_as_it_was() -> None:
    assert journal.shortened("37 log lines", limit=100) == "37 log lines"
