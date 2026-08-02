"""Composition root and entrypoint.

Dependency direction: imports every other layer. This is the only place
concrete adapters are named and injected, which is what keeps the rest of
the codebase free of them.
"""
