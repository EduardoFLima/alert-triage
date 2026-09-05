"""The settings a deployment is configured by, resolved and free of any source.

A consumer depends on these values, never on YAML files or environment
variables — which is what lets a test hand one a plain object and lets a
deployment choose its own source. The default values here are the documented
defaults from ``docs/vision.md``; an implementation resolves what an operator
supplied on top of them.

Values only: what a consumer asks for the whole of them through is ``Config``,
in ``port.py`` beside them.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import ClassVar


@dataclass(frozen=True)
class ServiceScope:
    """One service the job watches, and how urgently it is treated.

    Being listed is what puts a service in scope; the flag below says nothing
    about membership and everything about the tone of what is owed. An entry
    is only worth writing to raise that.

    Attributes:
        critical: Whether an incident on this service is investigated and
            reported with more urgency than one on any other in scope.
    """

    critical: bool = False


NOT_DECLARED = ServiceScope()
"""What a service nobody named resolves to: in scope on the owner's terms, and
not critical.

Answering an unnamed service with this rather than with ``None`` keeps every
caller reading one type, and puts the "not critical" answer where criticality
is stated rather than where the mapping is held.
"""


@dataclass(frozen=True)
class Scope:
    """What the job watches. Mandatory: there is no "watch everything" default.

    Two independent filters, each optional on its own and at least one of them
    resolved -- enforced where configuration is read, which is where a
    deployment can still be told what to set. Where both resolved they narrow
    together: the named services *of* that owner.

    Both are plain identifiers in this project's vocabulary. Spending them as
    query terms an observability platform understands is the alert source
    adapter's job, so this stays free of any one platform's naming.

    Attributes:
        owner: The single owner (v1: a team) whose alerts are in scope, or
            ``None`` where the run is bounded by its services alone.
        services: The services whose alerts are in scope, keyed by service
            name. Empty means the owner alone bounds the run.
    """

    owner: str | None = None
    services: Mapping[str, ServiceScope] = field(default_factory=dict)

    def for_service(self, service: str) -> ServiceScope:
        """What this scope says about one service, ``NOT_DECLARED`` where nothing.

        An owner-bounded run names no service and triages every service the
        owner owns, so a service absent from the mapping is the ordinary case
        rather than an error: what it gets back says it was declared nothing,
        which is what "not critical" means.
        """
        return self.services.get(service, NOT_DECLARED)


@dataclass(frozen=True)
class Grouping:
    """How far apart alerts of one service may fire and still be one incident.

    Attributes:
        window_seconds: The grouping time window, in seconds.
    """

    DEFAULT_WINDOW_SECONDS: ClassVar[int] = 1800

    window_seconds: int = DEFAULT_WINDOW_SECONDS

    @property
    def window(self) -> timedelta:
        """The window as a duration, which is what the grouping logic takes."""
        return timedelta(seconds=self.window_seconds)


@dataclass(frozen=True)
class Ingestion:
    """How a run fetches alerts: how far back it looks, and under what bounds.

    The request bounds are ingestion's own, deliberately not the ``mcp_*``
    circuit breakers: those bound an agent's tool calls during investigation,
    and the two will be tuned against different evidence. Equal starting
    defaults are not a shared concept.

    Attributes:
        lookback_seconds: How far back from the start of a run alerts are
            considered. Set comfortably wider than the interval the job runs
            on, so a delayed run does not step over alerts.
        request_timeout_seconds: Bound on a single request to the platform.
        max_retries: Retries of a failed request before the fetch gives up.
    """

    DEFAULT_LOOKBACK_SECONDS: ClassVar[int] = 3600

    lookback_seconds: int = DEFAULT_LOOKBACK_SECONDS
    request_timeout_seconds: int = 30
    max_retries: int = 3

    @property
    def lookback(self) -> timedelta:
        """The lookback as a duration, which is what a run subtracts from now."""
        return timedelta(seconds=self.lookback_seconds)


@dataclass(frozen=True)
class ReNotify:
    """How long a report suppresses the next one for the same incident.

    Attributes:
        cooldown_seconds: How long after reporting an incident the system
            waits before reporting it again, in seconds.
    """

    DEFAULT_COOLDOWN_SECONDS: ClassVar[int] = 172_800

    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS

    @property
    def cooldown(self) -> timedelta:
        """The cooldown as a duration, which is what the triage decision takes."""
        return timedelta(seconds=self.cooldown_seconds)


@dataclass(frozen=True)
class Ledger:
    """How much triage history is kept after an incident has closed.

    Deliberately its own section rather than a key under ``re_notify``: how
    long history is kept and how often a report repeats answer different
    questions, and neither is derived from the other. Where the ledger keeps
    its records is not here — a storage location is a deployment fact, read
    from the environment.

    Attributes:
        retention_seconds: How long a closed incident is kept for a human to
            consult before it is deleted, in seconds.
    """

    DEFAULT_RETENTION_SECONDS: ClassVar[int] = 2_592_000

    retention_seconds: int = DEFAULT_RETENTION_SECONDS

    @property
    def retention(self) -> timedelta:
        """The retention period as a duration, measured from when an incident closed."""
        return timedelta(seconds=self.retention_seconds)


@dataclass(frozen=True)
class SpecialistModel:
    """The model one specialist reasons on, where it differs from its siblings.

    A section keyed by specialist name rather than a field per specialist: a
    specialist is declared in the adapter that runs it, and the schema learns
    nothing when one is added.

    Attributes:
        model: The model that specialist runs on.
    """

    model: str


@dataclass(frozen=True)
class Investigation:
    """How an investigation reasons, and how many times it is given the chance.

    Behavior, not connection: which model reasons is a decision about how the
    system triages, while the credential that model needs is a deployment fact
    and lives in the environment.

    ``max_attempts`` is deliberately not ``circuit_breakers.max_mcp_retries``
    under another name. That bounds one call inside a single investigation;
    this bounds how many investigations an incident is given at all, across
    runs, and the two will be tuned against different evidence.

    Attributes:
        model: The model an investigation's agents run on, unless a specialist
            names its own.
        max_attempts: How many investigations one incident may be given in
            total, the first included, before the system stops trying and
            reports what fired without findings. One disables retrying.
        specialists: Per-specialist overrides, keyed by specialist name. Empty
            means every specialist reasons on ``model``.
    """

    DEFAULT_MODEL: ClassVar[str] = "gemini-2.5-flash"
    DEFAULT_MAX_ATTEMPTS: ClassVar[int] = 3

    model: str = DEFAULT_MODEL
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    specialists: Mapping[str, SpecialistModel] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject a bound that would leave every incident uninvestigable."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must allow at least one investigation")


@dataclass(frozen=True)
class CircuitBreakers:
    """Bounds on a multi-agent investigation, one per way it can run away.

    Attributes:
        max_tool_calls_per_agent: Tool calls one agent may make.
        max_agent_hops: Handoffs between agents in one investigation.
        max_investigation_duration_seconds: Wall-clock bound per investigation.
        max_mcp_retries: Retries of a failed MCP call.
        mcp_call_timeout_seconds: Timeout of a single MCP call.
    """

    max_tool_calls_per_agent: int = 8
    max_agent_hops: int = 2
    max_investigation_duration_seconds: int = 300
    max_mcp_retries: int = 3
    mcp_call_timeout_seconds: int = 30
