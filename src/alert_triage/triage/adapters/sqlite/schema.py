"""The shape of the ledger's storage: two tables and the indexes they are read by.

Kept apart from the queries that use it so that what the database *is* can be
read in one piece — by a human going back to inspect a retained incident with
any SQLite client as much as by the adapter.

Written to be applied unconditionally on every construction: a fresh
deployment gets its schema on first use and an existing one is left alone, so
there is no migration step to remember.

Instants are ``TEXT`` because SQLite has no datetime type. ISO-8601 sorts
correctly as text, which is what lets retention be a plain ``WHERE`` clause,
and it stays inspectable rather than becoming an opaque number.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id                     TEXT PRIMARY KEY,
    service                TEXT NOT NULL,
    last_reported_at       TEXT,
    closed_at              TEXT,
    investigation_attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS incident_alerts (
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    source_id   TEXT NOT NULL,
    service     TEXT NOT NULL,
    fired_at    TEXT NOT NULL,
    title       TEXT NOT NULL,
    link        TEXT NOT NULL,
    observed_latency_ms INTEGER
);
CREATE INDEX IF NOT EXISTS incidents_by_service ON incidents(service);
CREATE INDEX IF NOT EXISTS alerts_by_incident ON incident_alerts(incident_id);
"""

ADDED_COLUMNS = (
    "ALTER TABLE incidents ADD COLUMN "
    "investigation_attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE incident_alerts ADD COLUMN observed_latency_ms INTEGER",
)
"""Columns a table gained after the first version of it was already in use.

``CREATE TABLE IF NOT EXISTS`` leaves an existing table exactly as it stands,
so a column added to the statement above reaches a fresh deployment and no
other. SQLite has no ``ADD COLUMN IF NOT EXISTS``, so each of these is applied
and its "duplicate column" complaint ignored, which is idempotent for the same
reason the ``IF NOT EXISTS`` above is.

The default is what makes this need no backfill: an incident recorded before
the column existed reads back as having spent no attempts, which is the truth
about it. An alert recorded before its latency column existed reads back as
nobody having measured it, which is equally the truth — a latency that was
never stored was never read, and reading it as anything else would silence an
incident on a figure nobody supplied.
"""
