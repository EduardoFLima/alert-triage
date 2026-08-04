import importlib


def test_package_imports() -> None:
    module = importlib.import_module("alert_triage")

    assert module.__doc__ is not None


def test_layer_packages_import() -> None:
    for layer in ("domain", "ports", "adapters", "app"):
        assert importlib.import_module(f"alert_triage.{layer}") is not None
