"""Datadog as a provider to investigate on: its server, its addresses, its grammar.

What is Datadog's and nothing else's:

- where its MCP server lives and what authenticates against it;
- which tools it serves, in which toolset, and what each does;
- how the items a retrieval returned are addressed;
- the metric-query grammar every specialist asking one is taught;
- which of its preview toolsets an account may reach.

The specialists that query it are not here. A specialist's toolsets name the
providers serving them and may name more than one, so a declaration lives with
the crew in ``crew/`` and reaches this package for the provider it names.
Another provider is another directory beside this one, holding the same five
kinds of thing.
"""
