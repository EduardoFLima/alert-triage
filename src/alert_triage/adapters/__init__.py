"""Concrete implementations of the ports, one subpackage per integration.

Dependency direction: imports ``ports``, ``domain``, and its own vendor
library. An adapter is never imported by the layers it depends on.
"""
