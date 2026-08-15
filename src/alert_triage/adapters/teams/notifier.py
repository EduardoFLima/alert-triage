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
from contextlib import AbstractContextManager
from typing import Any, Protocol

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


class HttpResponse(Protocol):
    """What this adapter reads off an answer: whether it was taken, and why not."""

    @property
    def status(self) -> int:
        """The response status code."""

    def read(self) -> bytes:
        """The response body, which is where Workflows says what was wrong."""
        ...


class Opener(Protocol):
    """The one call this adapter makes, named so a test can stand in for it.

    Narrower than ``urllib.request.OpenerDirector``, on the same rule as the
    Datadog adapter's ``EventSearch``: a fake is a small class rather than a
    subclass of a stdlib one.
    """

    def open(
        self, request: urllib.request.Request, timeout: float
    ) -> AbstractContextManager[HttpResponse]:
        """Perform the request, bounded by the timeout."""
        ...


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

    The opener is injected rather than built here, on the same rule as the
    Datadog client and the SMTP factory: it is what lets these tests exercise
    the request, the timeout, and every failure path with no network at all.
    """

    def __init__(self, webhook_url: str, opener: Opener | None = None) -> None:
        """Bind the channel to its webhook and the opener it posts through.

        Args:
            webhook_url: The Workflows webhook the report is posted to.
            opener: Performs the request. Defaults to urllib's own.
        """
        self._webhook_url = webhook_url
        self._opener = opener if opener is not None else urllib.request.build_opener()

    def deliver(self, report: TriageReport) -> None:
        """Post the report as an Adaptive Card to the configured webhook.

        This is the boundary: past it a caller catches ``NotifierError`` and
        never learns HTTP was involved.
        """
        try:
            self._post(render(report), report)
        except urllib.error.HTTPError as error:
            raise self._failure(report, f"{error.code} {_read(error)}") from error
        except (urllib.error.URLError, OSError) as error:
            raise self._failure(report, str(error)) from error

    def _post(self, envelope: dict[str, Any], report: TriageReport) -> None:
        """Send the envelope and insist the destination said it took it."""
        with self._opener.open(
            _request(self._webhook_url, envelope), timeout=TIMEOUT_SECONDS
        ) as response:
            status = response.status
            if not 200 <= status < 300:
                raise self._failure(report, f"{status} {_decoded(response.read())}")

    def _failure(self, report: TriageReport, said: str) -> NotifierError:
        """Name the incident, the destination, and what the destination said."""
        return NotifierError(
            f"Could not post the report for incident {report.incident_id!r} to the "
            f"Teams webhook: {said}"
        )


def _request(webhook_url: str, envelope: dict[str, Any]) -> urllib.request.Request:
    """Build the POST that carries one envelope."""
    return urllib.request.Request(
        webhook_url,
        data=json.dumps(envelope).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def _read(error: urllib.error.HTTPError) -> str:
    """Read the body of a rejection, which is where Workflows says what was wrong.

    A body that has already been consumed or closed answers ``ValueError``
    rather than ``OSError``, so both are caught: the status and the reason are
    still worth reporting, and a failure to read the explanation must not
    replace the failure being explained.
    """
    try:
        return _decoded(error.read())
    except (OSError, ValueError):
        return error.reason if isinstance(error.reason, str) else str(error.reason)


def _decoded(body: bytes) -> str:
    """Read a response body as text, whatever the destination encoded it as."""
    return body.decode("utf-8", errors="replace")
