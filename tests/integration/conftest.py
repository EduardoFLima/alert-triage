"""Fixtures shared by the integration tests, whatever they exercise."""

import socket
import urllib.error
import urllib.request
from collections.abc import Callable

import pytest

ANSWER_TIMEOUT_SECONDS = 30.0
"""How long a page is given to answer before the check gives up on it."""


@pytest.fixture
def answers() -> Callable[[str], bool]:
    """Whether the platform serves a page at an address this project built.

    A fixture rather than a helper module, so the check travels the way every
    other shared piece of these tests does.
    """
    return _answers


def _answers(address: str) -> bool:
    """Follow one address and say whether the platform served anything.

    The one thing no fake establishes: that a URL form this project composes
    is a route the platform actually accepts. A redirect to a login page is an
    answer — these are UI addresses and the check holds no session — so what
    is being ruled out is the 404 that a route built from the wrong kind of
    identifier returns.
    """
    request = urllib.request.Request(address, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=ANSWER_TIMEOUT_SECONDS) as answer:
            return int(answer.status) < 400
    except urllib.error.HTTPError as refused:
        return int(refused.code) != 404
    except urllib.error.URLError:
        return False


@pytest.fixture
def free_port() -> int:
    """A port nothing is listening on, found by binding one and letting it go."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
