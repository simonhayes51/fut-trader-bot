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


-- Retire trading-heavy progression from the Discord community bot.
UPDATE quest_definitions
SET active=false,updated_at=now()
WHERE quest_key IN ('daily_trade','weekly_trader','weekly_investor')
   OR event_type IN ('trade_logged','investment_join');

UPDATE achievement_definitions
SET active=false
WHERE achievement_key='trader_10';

UPDATE achievement_definitions
SET name='Community regular',description='Reached level 10.'
WHERE achievement_key='level_10';

INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'daily_kudos','Give kudos','Recognise another member for a useful contribution.','daily','kudos_given',1,50,25,30
FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;

INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'weekly_kudos','Community champion','Give kudos to five useful contributions this week.','weekly','kudos_given',5,250,150,120
FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;

INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'weekly_streak','Stay consistent','Claim your daily reward five times this week.','weekly','daily_claim',5,150,100,140
FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;

INSERT INTO achievement_definitions(guild_id,achievement_key,name,description,icon,xp_reward,coin_reward,sort_order)
SELECT guild_id,'kudos_10','Recognised member','Received ten kudos from the community.','👏',200,250,80
FROM guild_settings ON CONFLICT(guild_id,achievement_key) DO NOTHING;
