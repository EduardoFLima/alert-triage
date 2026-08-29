"""Which of Datadog's Preview toolsets this deployment's account may reach.

One switch, read by every specialist that would otherwise declare a tool the
account cannot call. A tool the server will not admit is worse than a missing
one: the model is told it has it, spends a call discovering it does not, and
the refusal comes back as a failed retrieval — which marks the whole
investigation incomplete for a capability nobody ever had.

It lives in code rather than in ``config.yaml`` deliberately. What a specialist
may ask is its identity, and the instruction that assumes those tools has to
change with them — the two cannot be tuned apart, which is exactly why
``docs/vision.md`` keeps tool lists out of operator settings. This switch flips
both at once, which is the only way the pair stays honest.

It is not a feature flag to leave standing. Preview toolsets go generally
available; when ``apm`` does, this constant and the branches it drives come out
and the declarations keep only their fuller form.
"""

APM_TOOLSET_AVAILABLE = False
"""Whether this account can reach Datadog's ``apm`` toolset, which is in Preview.

Set to ``True`` when Datadog grants the account access. Two specialists widen
when it flips, and nothing else in the codebase has to change:

- the APM specialist regains latency-bottleneck breakdown, the platform's own
  Watchdog anomalies, and change stories in place of raw events;
- the trace specialist regains ranking within a trace rather than reading one
  whole.

The credential-gated live test is what confirms the account really has it: this
constant states an intent and the server settles it.
"""
