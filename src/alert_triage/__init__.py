"""Alert Triage: first-pass investigation of observability alerts.

The package is laid out as a hexagon. Dependencies point inward only:
``app`` -> ``adapters`` -> ``ports`` -> ``domain``. See ``docs/vision.md``
for the architecture this layout implements.
"""
