CREATE TABLE IF NOT EXISTS health_scan_state (
  guild_id TEXT PRIMARY KEY,
  scanned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finding_count INTEGER NOT NULL DEFAULT 0 CHECK (finding_count >= 0)
);
