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
    id               TEXT PRIMARY KEY,
    service          TEXT NOT NULL,
    last_reported_at TEXT,
    closed_at        TEXT
);
CREATE TABLE IF NOT EXISTS incident_alerts (
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    source_id   TEXT NOT NULL,
    service     TEXT NOT NULL,
    fired_at    TEXT NOT NULL,
    title       TEXT NOT NULL,
    link        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS incidents_by_service ON incidents(service);
CREATE INDEX IF NOT EXISTS alerts_by_incident ON incident_alerts(incident_id);
"""
