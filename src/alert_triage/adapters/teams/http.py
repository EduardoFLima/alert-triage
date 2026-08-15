"""How this adapter reaches the webhook, and how it is stood in for.

Every ``urllib`` type lives here, so ``notifier`` is left with what a report
looks like as a card rather than how an HTTP request behaves.
"""

import urllib.error
import urllib.request
from collections.abc import Callable

# A hung destination must not hold a run open. Fixed rather than configurable,
# for the same reason as the mail channel's.
TIMEOUT_SECONDS = 30

type Post = Callable[[str, bytes], tuple[int, bytes]]
"""Send a JSON body to a URL, answering the status and the response body.

The whole seam this adapter needs, as one function rather than a client
object: a test stands in with a two-line function, and the answer is already
read — so there is no stream left for anything downstream to find consumed.
"""


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
