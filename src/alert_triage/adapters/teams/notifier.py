"""Posting a triage report to Microsoft Teams as an Adaptive Card.

Everything Teams-shaped stops here: the message envelope, the card schema, the
HTTP request, and what a non-2xx answer means. What leaves is nothing, or a
``NotifierError``.

The destination is a Power Automate Workflows webhook — the supported
successor to the Office 365 connector webhooks Microsoft retired, and the one
that keeps the deployment shape this project wants: a single URL in the
environment, no app registration and no token flow.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from alert_triage.domain.report import TriageReport
from alert_triage.ports.notifier import NotifierError

ADAPTIVE_CARD_CONTENT_TYPE = "application/vnd.microsoft.card.adaptive"
CARD_SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"

# The version Microsoft's own incoming-webhook example declares. Nothing in
# this card needs a later one, and asking for one a client cannot render costs
# a report its formatting for nothing.
CARD_VERSION = "1.2"

# A hung destination must not hold a run open. Fixed rather than configurable,
# for the same reason as the mail channel's.
TIMEOUT_SECONDS = 30


type Post = Callable[[str, bytes], tuple[int, bytes]]
"""Send a JSON body to a URL, answering the status and the response body.

The whole seam this adapter needs, as one function rather than a client
object: every `urllib` type stays behind it, a test stands in with a two-line
function, and the answer is already read — so there is no stream left for
anything downstream to find consumed.
"""


def render(report: TriageReport) -> dict[str, Any]:
    """Render a report as the message a Teams webhook accepts.

    Pure, so the shape of what gets posted is tested without an HTTP server.

    Args:
        report: The report to render.

    Returns:
        The message envelope, carrying one Adaptive Card whose heading is the
        report's subject and whose text is its body, verbatim.
    """
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": ADAPTIVE_CARD_CONTENT_TYPE,
                "contentUrl": None,
                "content": {
                    "$schema": CARD_SCHEMA,
                    "type": "AdaptiveCard",
                    "version": CARD_VERSION,
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": report.subject,
                            "weight": "bolder",
                            "size": "medium",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": report.body,
                            "wrap": True,
                        },
                    ],
                },
            }
        ],
    }


class TeamsNotifier:
    """A ``Notifier`` that posts each report to a Teams Workflows webhook.

    How the POST is performed is injected, on the same rule as the Datadog
    client and the SMTP factory: it is what lets these tests exercise the
    envelope and every failure path with no network at all.
    """

    def __init__(self, webhook_url: str, post: Post | None = None) -> None:
        """Bind the channel to its webhook and the way it posts.

        Args:
            webhook_url: The Workflows webhook the report is posted to.
            post: Performs the POST. Defaults to urllib's.
        """
        self._webhook_url = webhook_url
        self._post = post if post is not None else post_over_urllib

    def deliver(self, report: TriageReport) -> None:
        """Post the report as an Adaptive Card to the configured webhook.

        This is the boundary: past it a caller catches ``NotifierError`` and
        never learns HTTP was involved.
        """
        try:
            status, answer = self._post(self._webhook_url, _encoded(render(report)))
        except OSError as error:
            raise self._failure(report, str(error)) from error
        if not 200 <= status < 300:
            raise self._failure(report, f"{status} {_decoded(answer)}")

    def _failure(self, report: TriageReport, said: str) -> NotifierError:
        """Name the incident, the destination, and what the destination said."""
        return NotifierError(
            f"Could not post the report for incident {report.incident_id!r} to the "
            f"Teams webhook: {said}"
        )


def post_over_urllib(url: str, body: bytes) -> tuple[int, bytes]:
    """POST a JSON body over the standard library, bounded by the fixed timeout.

    A rejection is read here rather than raised onward: ``urllib`` reports a
    non-2xx as an ``HTTPError`` that is both the failure and the response, and
    its body is readable exactly once. Reading it in the same breath as
    catching it is what makes the status and the explanation available
    together, and what leaves no half-consumed stream behind.
    """
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as rejection:
        with rejection:
            return rejection.code, rejection.read()


def _encoded(envelope: dict[str, Any]) -> bytes:
    """Encode one envelope as the JSON body that carries it."""
    return json.dumps(envelope).encode("utf-8")


def _decoded(body: bytes) -> str:
    """Read a response body as text, whatever the destination encoded it as."""
    return body.decode("utf-8", errors="replace")
