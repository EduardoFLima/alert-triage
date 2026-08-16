"""``python -m alert_triage``: the same job the console script runs.

Kept to one line of behavior on purpose — the entrypoint itself is in
``app.main``, so the two ways of starting a run cannot drift apart.
"""

import sys

from alert_triage.app.main import main

sys.exit(main())
