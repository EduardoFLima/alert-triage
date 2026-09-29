import urllib.error
import urllib.request
from collections.abc import Callable

# A hung destination must not hold a run open. Fixed rather than configurable,
# for the same reason as the mail channel's.
TIMEOUT_SECONDS = 30

type Post = Callable[[str, bytes], tuple[int, bytes]]


def post_over_urllib(url: str, body: bytes) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    # HTTPError is also the response, and its body can be read only once.
    except urllib.error.HTTPError as rejection:
        with rejection:
            return rejection.code, rejection.read()
