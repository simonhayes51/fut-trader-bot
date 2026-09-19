-- Community features v4: Discord-first tools only.

CREATE TABLE IF NOT EXISTS starboard_posts (
  guild_id TEXT NOT NULL,
  source_message_id TEXT NOT NULL,
  source_channel_id TEXT NOT NULL,
  starboard_message_id TEXT,
  reaction_count INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,source_message_id)
);

CREATE TABLE IF NOT EXISTS custom_responses (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  trigger TEXT NOT NULL,
  response TEXT NOT NULL,
  match_mode TEXT NOT NULL DEFAULT 'contains' CHECK (match_mode IN ('exact','contains','starts_with')),
  channel_ids TEXT[] NOT NULL DEFAULT '{}',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  cooldown_seconds INTEGER NOT NULL DEFAULT 30,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS custom_responses_guild_idx ON custom_responses(guild_id,enabled);

CREATE TABLE IF NOT EXISTS sticky_messages (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  content TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  min_interval_seconds INTEGER NOT NULL DEFAULT 300,
  last_message_id TEXT,
  last_posted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(guild_id,channel_id)
);

CREATE TABLE IF NOT EXISTS response_cooldowns (
  guild_id TEXT NOT NULL,
  response_id BIGINT NOT NULL REFERENCES custom_responses(id) ON DELETE CASCADE,
  channel_id TEXT NOT NULL,
  next_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(guild_id,response_id,channel_id)
);
