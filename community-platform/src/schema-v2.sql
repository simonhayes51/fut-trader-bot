ALTER TABLE tickets ADD COLUMN IF NOT EXISTS claimed_by TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS close_reason TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS transcript TEXT;
ALTER TABLE member_stats ADD COLUMN IF NOT EXISTS helpful_actions BIGINT NOT NULL DEFAULT 0;
ALTER TABLE member_stats ADD COLUMN IF NOT EXISTS streak_days INTEGER NOT NULL DEFAULT 0;
ALTER TABLE member_stats ADD COLUMN IF NOT EXISTS last_active_date DATE;

CREATE TABLE IF NOT EXISTS trade_journal (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,player TEXT NOT NULL,buy_price BIGINT NOT NULL,sell_price BIGINT,quantity INTEGER NOT NULL DEFAULT 1,status TEXT NOT NULL DEFAULT 'OPEN',profit BIGINT,notes TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),closed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS portfolio_positions (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,item TEXT NOT NULL,buy_price BIGINT NOT NULL,quantity INTEGER NOT NULL DEFAULT 1,target_price BIGINT,notes TEXT,status TEXT NOT NULL DEFAULT 'OPEN',created_at TIMESTAMPTZ NOT NULL DEFAULT now(),closed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS investments (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,title TEXT NOT NULL,buy_price BIGINT,target_price BIGINT,reason TEXT,status TEXT NOT NULL DEFAULT 'LIVE',result_price BIGINT,discord_message_id TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),closed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS investment_entries (
 investment_id BIGINT NOT NULL REFERENCES investments(id) ON DELETE CASCADE,user_id TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),PRIMARY KEY(investment_id,user_id)
);
CREATE TABLE IF NOT EXISTS price_checks (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,item TEXT NOT NULL,price BIGINT,image_url TEXT,discord_message_id TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),closed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS market_sentiment (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,topic TEXT NOT NULL,discord_message_id TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),closed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS glossary (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,term TEXT NOT NULL,definition TEXT NOT NULL,created_by TEXT,updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),UNIQUE(guild_id,term)
);
CREATE TABLE IF NOT EXISTS achievements (
 guild_id TEXT NOT NULL,user_id TEXT NOT NULL,achievement_key TEXT NOT NULL,awarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),PRIMARY KEY(guild_id,user_id,achievement_key)
);
CREATE TABLE IF NOT EXISTS giveaways (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,channel_id TEXT NOT NULL,message_id TEXT,prize TEXT NOT NULL,winner_count INTEGER NOT NULL DEFAULT 1,required_role_id TEXT,premium_bonus_entries INTEGER NOT NULL DEFAULT 0,min_account_age_days INTEGER NOT NULL DEFAULT 0,ends_at TIMESTAMPTZ NOT NULL,status TEXT NOT NULL DEFAULT 'LIVE',winners TEXT[] NOT NULL DEFAULT '{}',created_by TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS giveaway_entries (
 giveaway_id BIGINT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,user_id TEXT NOT NULL,entries INTEGER NOT NULL DEFAULT 1,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),PRIMARY KEY(giveaway_id,user_id)
);
CREATE TABLE IF NOT EXISTS staff_notes (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,staff_id TEXT NOT NULL,note TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS scam_cases (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,reporter_id TEXT NOT NULL,accused_id TEXT,evidence TEXT,status TEXT NOT NULL DEFAULT 'OPEN',assigned_to TEXT,resolution TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),closed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS temp_rooms (
 id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,channel_id TEXT NOT NULL,owner_id TEXT NOT NULL,name TEXT NOT NULL,expires_at TIMESTAMPTZ,status TEXT NOT NULL DEFAULT 'OPEN',created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS command_settings (
 guild_id TEXT NOT NULL,command_name TEXT NOT NULL,enabled BOOLEAN NOT NULL DEFAULT TRUE,role_ids TEXT[] NOT NULL DEFAULT '{}',channel_ids TEXT[] NOT NULL DEFAULT '{}',premium_only BOOLEAN NOT NULL DEFAULT FALSE,updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),PRIMARY KEY(guild_id,command_name)
);
CREATE TABLE IF NOT EXISTS member_links (
 guild_id TEXT NOT NULL,user_id TEXT NOT NULL,provider TEXT NOT NULL,external_id TEXT,metadata JSONB NOT NULL DEFAULT '{}'::jsonb,verified_at TIMESTAMPTZ NOT NULL DEFAULT now(),PRIMARY KEY(guild_id,user_id,provider)
);
CREATE TABLE IF NOT EXISTS activity_daily (
 guild_id TEXT NOT NULL,user_id TEXT NOT NULL,activity_date DATE NOT NULL,messages INTEGER NOT NULL DEFAULT 0,xp BIGINT NOT NULL DEFAULT 0,helpful INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(guild_id,user_id,activity_date)
);
CREATE TABLE IF NOT EXISTS server_metrics_daily (
 guild_id TEXT NOT NULL,metric_date DATE NOT NULL,joins INTEGER NOT NULL DEFAULT 0,leaves INTEGER NOT NULL DEFAULT 0,messages INTEGER NOT NULL DEFAULT 0,trade_calls INTEGER NOT NULL DEFAULT 0,tickets_opened INTEGER NOT NULL DEFAULT 0,premium_conversions INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(guild_id,metric_date)
);
CREATE TABLE IF NOT EXISTS setup_state (
 guild_id TEXT PRIMARY KEY,completed BOOLEAN NOT NULL DEFAULT FALSE,last_health_score INTEGER NOT NULL DEFAULT 0,updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_journal_user ON trade_journal(guild_id,user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_portfolio_user ON portfolio_positions(guild_id,user_id,status);
CREATE INDEX IF NOT EXISTS idx_giveaways_due ON giveaways(guild_id,status,ends_at);
CREATE INDEX IF NOT EXISTS idx_staff_notes_user ON staff_notes(guild_id,user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON server_metrics_daily(guild_id,metric_date DESC);

INSERT INTO glossary(guild_id,term,definition,created_by) SELECT guild_id,'fodder','Cards valued mainly for their rating and SBC usefulness rather than gameplay.',NULL FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO glossary(guild_id,term,definition,created_by) SELECT guild_id,'lazy buyer','A buyer who pays above the cheapest market price instead of searching for the lowest listing.',NULL FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO glossary(guild_id,term,definition,created_by) SELECT guild_id,'panic sell','Selling quickly because the market is falling or expected to fall, often accepting a lower price.',NULL FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO glossary(guild_id,term,definition,created_by) SELECT guild_id,'out of packs','A card that can no longer be packed, so new supply stops entering the market.',NULL FROM guild_settings ON CONFLICT DO NOTHING;
