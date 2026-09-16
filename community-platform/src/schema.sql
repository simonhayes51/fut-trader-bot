CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id TEXT PRIMARY KEY,
  guild_name TEXT,
  settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS feature_settings (
  guild_id TEXT NOT NULL, feature_key TEXT NOT NULL, enabled BOOLEAN NOT NULL DEFAULT TRUE,
  config JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (guild_id, feature_key)
);
CREATE TABLE IF NOT EXISTS member_stats (
  guild_id TEXT NOT NULL,user_id TEXT NOT NULL,xp BIGINT NOT NULL DEFAULT 0,messages BIGINT NOT NULL DEFAULT 0,
  thanks_received BIGINT NOT NULL DEFAULT 0,thanks_given BIGINT NOT NULL DEFAULT 0,trade_calls BIGINT NOT NULL DEFAULT 0,
  successful_calls BIGINT NOT NULL DEFAULT 0,last_message_at TIMESTAMPTZ,PRIMARY KEY (guild_id,user_id)
);
CREATE TABLE IF NOT EXISTS reputation_events (id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,giver_id TEXT NOT NULL,receiver_id TEXT NOT NULL,reason TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS trade_calls (id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,player TEXT NOT NULL,buy_price BIGINT,target_price BIGINT,reason TEXT,status TEXT NOT NULL DEFAULT 'LIVE',result_price BIGINT,discord_message_id TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),closed_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS suggestions (id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Submitted',discord_message_id TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS warnings (id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,moderator_id TEXT NOT NULL,reason TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS tickets (id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,user_id TEXT NOT NULL,ticket_type TEXT NOT NULL,channel_id TEXT,status TEXT NOT NULL DEFAULT 'OPEN',created_at TIMESTAMPTZ NOT NULL DEFAULT now(),closed_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS social_feeds (id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,name TEXT NOT NULL,provider TEXT NOT NULL,source TEXT NOT NULL,channel_id TEXT NOT NULL,enabled BOOLEAN NOT NULL DEFAULT TRUE,include_keywords TEXT[] NOT NULL DEFAULT '{}',exclude_keywords TEXT[] NOT NULL DEFAULT '{}',mention_role_id TEXT,last_item_id TEXT,secret_key TEXT UNIQUE,config JSONB NOT NULL DEFAULT '{}'::jsonb,updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS scheduled_messages (id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,name TEXT NOT NULL,channel_id TEXT NOT NULL,cron_expression TEXT NOT NULL,content TEXT NOT NULL,enabled BOOLEAN NOT NULL DEFAULT TRUE,last_sent_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS audit_log (id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,actor_id TEXT,action TEXT NOT NULL,details JSONB NOT NULL DEFAULT '{}'::jsonb,created_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS billing_plans (
  id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,name TEXT NOT NULL,slug TEXT NOT NULL,description TEXT,
  stripe_price_id TEXT NOT NULL,role_id TEXT NOT NULL,active BOOLEAN NOT NULL DEFAULT TRUE,trial_days INTEGER NOT NULL DEFAULT 0,
  sort_order INTEGER NOT NULL DEFAULT 0,metadata JSONB NOT NULL DEFAULT '{}'::jsonb,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(guild_id,slug)
);
CREATE TABLE IF NOT EXISTS billing_customers (
  guild_id TEXT NOT NULL,discord_user_id TEXT NOT NULL,stripe_customer_id TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,discord_user_id),UNIQUE(stripe_customer_id)
);
CREATE TABLE IF NOT EXISTS billing_subscriptions (
  id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,discord_user_id TEXT NOT NULL,plan_id BIGINT REFERENCES billing_plans(id) ON DELETE SET NULL,
  stripe_subscription_id TEXT UNIQUE,stripe_customer_id TEXT,status TEXT NOT NULL,current_period_end TIMESTAMPTZ,cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
  referral_code TEXT,source TEXT NOT NULL DEFAULT 'stripe',created_at TIMESTAMPTZ NOT NULL DEFAULT now(),updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS entitlements (
  id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,discord_user_id TEXT NOT NULL,entitlement_key TEXT NOT NULL,source TEXT NOT NULL,source_ref TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,expires_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(guild_id,discord_user_id,entitlement_key)
);
CREATE TABLE IF NOT EXISTS referral_codes (
  id BIGSERIAL PRIMARY KEY,guild_id TEXT NOT NULL,owner_discord_user_id TEXT,code TEXT NOT NULL,active BOOLEAN NOT NULL DEFAULT TRUE,
  reward_type TEXT NOT NULL DEFAULT 'none',reward_value NUMERIC(12,2) NOT NULL DEFAULT 0,clicks BIGINT NOT NULL DEFAULT 0,conversions BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),UNIQUE(guild_id,code)
);
CREATE TABLE IF NOT EXISTS billing_events (
  id BIGSERIAL PRIMARY KEY,stripe_event_id TEXT NOT NULL UNIQUE,event_type TEXT NOT NULL,payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  processed_at TIMESTAMPTZ,error TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS user_sessions (
  sid TEXT PRIMARY KEY,
  sess JSONB NOT NULL,
  expire TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_log_guild_created ON audit_log(guild_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rep_guild_receiver ON reputation_events(guild_id,receiver_id);
CREATE INDEX IF NOT EXISTS idx_calls_guild_user ON trade_calls(guild_id,user_id);
CREATE INDEX IF NOT EXISTS idx_social_enabled ON social_feeds(guild_id,enabled);
CREATE INDEX IF NOT EXISTS idx_billing_sub_guild_user ON billing_subscriptions(guild_id,discord_user_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_entitlements_active ON entitlements(guild_id,discord_user_id,active);
CREATE INDEX IF NOT EXISTS idx_billing_events_created ON billing_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expire ON user_sessions(expire);
