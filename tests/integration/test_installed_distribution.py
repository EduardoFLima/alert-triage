from importlib import metadata
from pathlib import Path

import alert_triage


def test_package_is_installed_not_imported_from_the_working_directory() -> None:
    """The ``src/`` layout only pays off if tests import the installed package."""
    assert metadata.version("alert-triage")

    package_root = Path(alert_triage.__file__).parent
    assert package_root.name == "alert_triage"
    assert package_root.parent.name == "src"
