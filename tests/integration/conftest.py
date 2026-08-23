"""Fixtures shared by the integration tests, whatever they exercise."""

import socket

import pytest


@pytest.fixture
def free_port() -> int:
    """A port nothing is listening on, found by binding one and letting it go."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
