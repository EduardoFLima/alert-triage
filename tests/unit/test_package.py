import importlib


def test_package_imports() -> None:
    module = importlib.import_module("alert_triage")

    assert module.__doc__ is not None


def test_every_context_package_imports() -> None:
    for context in (
        "shared",
        "configuration",
        "triage",
        "investigation",
        "notification",
        "app",
    ):
        assert importlib.import_module(f"alert_triage.{context}") is not None
