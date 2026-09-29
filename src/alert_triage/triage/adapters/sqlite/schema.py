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
    link        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS incidents_by_service ON incidents(service);
CREATE INDEX IF NOT EXISTS alerts_by_incident ON incident_alerts(incident_id);
"""

ADDED_COLUMNS = (
    "ALTER TABLE incidents ADD COLUMN "
    "investigation_attempts INTEGER NOT NULL DEFAULT 0",
)
