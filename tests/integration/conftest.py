import socket
import urllib.error
import urllib.request
from collections.abc import Callable

import pytest

ANSWER_TIMEOUT_SECONDS = 30.0


@pytest.fixture
def answers() -> Callable[[str], bool]:
    return _answers


def _answers(address: str) -> bool:
    """Treat login redirects as answers; only a 404 rejects the route shape."""
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
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def free_ports() -> tuple[int, int]:
    """Hold both probes open so the OS cannot offer the same port twice."""
    with socket.socket() as one, socket.socket() as other:
        one.bind(("127.0.0.1", 0))
        other.bind(("127.0.0.1", 0))
        return int(one.getsockname()[1]), int(other.getsockname()[1])
