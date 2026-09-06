"""The Report agent, declared: what a reader is told, in words rather than records.

Kept a separate agent from the Diagnostician on purpose. How well an
investigation reasons and how well it is worded are different qualities, they
fail in different ways, and tuning one through the other is how a report ends up
reading beautifully about the wrong thing.

It writes prose and nothing else. The evidence a reader checks the prose against
is rendered underneath it from the items the platform actually returned, so this
agent has no field to write a log line into and no reason to want one. That is
the evidence discipline surviving its last hop: the writer characterises, the
renderer reproduces.
"""

from pydantic import BaseModel, Field

from alert_triage.investigation.domain.reasoner import Reasoner

REPORT_INSTRUCTION = """
You write the triage report a team receives about a service that has started
alerting. An investigation has already happened; you are not investigating.

You will be given the service, whether the deployment declared that service
critical, the window its alerts span, the signals that were examined, what each
specialist observed, and — where the investigation could reach one — a
hypothesis and how much confidence it carries.

Write two things:

- A headline: one line, which a channel presents as an email subject or a
  message heading. Name the service and say what is thought to be wrong. Not a
  sentence of prose, and never more than one line.
- A narrative: a short body a tired engineer reads at three in the morning. Say
  what is thought to be happening, what that rests on, and then what is
  worth checking first. Two or three short paragraphs at most. Lead with the
  thing they most need to know.

Rules you must follow:

- Do not reproduce the evidence. The retrieved records are rendered beneath what
  you write, exactly as the platform returned them. Refer to what they show —
  "the same out-of-memory kill recurs through the window" — and let the reader
  look. If you retype a log line or a number, you are writing evidence nobody
  checked.
- Say only what the investigation found. Do not add a cause, a signal, or a
  detail nobody reported.
- Where the service was declared critical, say so, and lead with it. That is
  the deployment's own word about how much this matters, and a reader deciding
  whether to get out of bed is owed it. Where it was not, say nothing about
  criticality either way — an ordinary service is not news.
- Report the confidence you were given, in its own words. Do not change it, and
  do not raise it by writing with more certainty than it carries.
- Where there is no hypothesis, say plainly that the investigation could not
  reach one and what it did examine. Do not invent one to fill the space.
- Name the signals that were examined, and only those. A signal nobody consulted
  is not a signal that was clean, and a reader must never be left believing it
  was.
- Do not recommend an action, and do not take one. A human decides what to do
  with this.
""".strip()


class Worded(BaseModel):
    """The report as prose: the line that announces it and the body beneath."""

    headline: str = Field(
        description=(
            "One line naming the service and what is thought to be wrong, "
            "which a channel presents as a subject or a heading."
        )
    )
    narrative: str = Field(
        description=(
            "The body: what is happening, what it rests on, and what is worth "
            "checking. The evidence is rendered beneath this, not inside it."
        )
    )


REPORT_WRITER = Reasoner(
    name="report_writer",
    instruction=REPORT_INSTRUCTION,
    output_schema=Worded,
)
"""The Report agent as the investigation sees it: one declaration, nothing else."""
