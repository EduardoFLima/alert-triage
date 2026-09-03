"""The crew: every agent this context runs, declared as data.

Two kinds, siblings rather than one filed under the other. ``specialists/``
gather evidence from observability providers; ``reasoners/`` reason over what
the specialists brought back and reach no provider at all. ``roster.py`` says
which of them exist.

A declaration lives here rather than under the provider it queries. A
specialist's toolsets name the providers serving them, and a specialist may
name more than one — so filing it by platform would give a declaration a choice
of two homes and no honest answer. What is Datadog's, and only Datadog's, is
next door in ``datadog/``: where its server is, how its items are addressed,
and the grammar its queries are written in. What is the framework's is in
``adk/``: the machinery that turns one of these declarations into a running
agent.
"""
