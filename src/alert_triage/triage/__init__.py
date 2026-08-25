"""Triage: what fired, what it amounts to, and what is owed about it.

The core context. It owns the Incident aggregate, the grouping that opens one,
and the policy deciding what a run does about it — and it is the customer of
the two supporting contexts, asking one to investigate and the other to
deliver, through the contracts they publish.
"""
