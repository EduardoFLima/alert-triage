"""The agents that reason over what the specialists brought back.

Two of them: the Diagnostician, which decides what to consult and concludes
across the answers, and the Report agent, which words the account. Neither
queries a provider, which is why neither declares a toolset — but they are the
specialists' siblings for all that, and sit beside them rather than under the
framework that happens to run all three.
"""
