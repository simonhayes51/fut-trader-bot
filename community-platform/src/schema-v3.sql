-- EAFC.Live Community Economy v3
-- Progression, rewards, quests, seasons and a spendable Live Coins economy.

CREATE TABLE IF NOT EXISTS economy_settings (
  guild_id TEXT PRIMARY KEY,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  xp_per_message INTEGER NOT NULL DEFAULT 4,
  coins_per_message INTEGER NOT NULL DEFAULT 1,
  message_cooldown_seconds INTEGER NOT NULL DEFAULT 60,
  daily_message_xp_cap INTEGER NOT NULL DEFAULT 200,
  daily_message_coin_cap INTEGER NOT NULL DEFAULT 40,
  daily_claim_coins INTEGER NOT NULL DEFAULT 25,
  streak_bonus_per_day INTEGER NOT NULL DEFAULT 5,
  streak_bonus_cap INTEGER NOT NULL DEFAULT 50,
  helpful_xp INTEGER NOT NULL DEFAULT 30,
  helpful_coins INTEGER NOT NULL DEFAULT 15,
  referral_xp INTEGER NOT NULL DEFAULT 250,
  referral_coins INTEGER NOT NULL DEFAULT 500,
  trade_xp INTEGER NOT NULL DEFAULT 20,
  trade_coins INTEGER NOT NULL DEFAULT 5,
  join_xp INTEGER NOT NULL DEFAULT 25,
  join_coins INTEGER NOT NULL DEFAULT 25,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS member_economy (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  xp_total BIGINT NOT NULL DEFAULT 0,
  coins_balance BIGINT NOT NULL DEFAULT 0,
  lifetime_coins_earned BIGINT NOT NULL DEFAULT 0,
  lifetime_coins_spent BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id),
  CHECK (coins_balance >= 0)
);

CREATE TABLE IF NOT EXISTS economy_ledger (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  currency TEXT NOT NULL CHECK (currency IN ('xp','coins')),
  amount BIGINT NOT NULL,
  reason TEXT NOT NULL,
  source_type TEXT,
  source_id TEXT,
  idempotency_key TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS economy_ledger_idempotency_idx
  ON economy_ledger(guild_id,idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS economy_ledger_member_idx
  ON economy_ledger(guild_id,user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS economy_ledger_created_idx
  ON economy_ledger(guild_id,created_at DESC);

CREATE TABLE IF NOT EXISTS economy_daily_caps (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  cap_date DATE NOT NULL,
  message_xp INTEGER NOT NULL DEFAULT 0,
  message_coins INTEGER NOT NULL DEFAULT 0,
  rewarded_messages INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(guild_id,user_id,cap_date)
);

CREATE TABLE IF NOT EXISTS economy_cooldowns (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  cooldown_key TEXT NOT NULL,
  next_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id,cooldown_key)
);

CREATE TABLE IF NOT EXISTS member_streaks (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  current_streak INTEGER NOT NULL DEFAULT 0,
  longest_streak INTEGER NOT NULL DEFAULT 0,
  last_claim_date DATE,
  last_activity_date DATE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id)
);

CREATE TABLE IF NOT EXISTS economy_seasons (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  name TEXT NOT NULL,
  starts_at TIMESTAMPTZ NOT NULL,
  ends_at TIMESTAMPTZ NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  rewards JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS economy_one_active_season_idx
  ON economy_seasons(guild_id) WHERE active=TRUE;

CREATE TABLE IF NOT EXISTS season_member_stats (
  season_id BIGINT NOT NULL REFERENCES economy_seasons(id) ON DELETE CASCADE,
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  xp_earned BIGINT NOT NULL DEFAULT 0,
  coins_earned BIGINT NOT NULL DEFAULT 0,
  quests_completed INTEGER NOT NULL DEFAULT 0,
  helpful_actions INTEGER NOT NULL DEFAULT 0,
  trades_logged INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(season_id,user_id)
);
CREATE INDEX IF NOT EXISTS season_member_rank_idx
  ON season_member_stats(season_id,xp_earned DESC);

CREATE TABLE IF NOT EXISTS quest_definitions (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  quest_key TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  cadence TEXT NOT NULL CHECK (cadence IN ('daily','weekly','season','lifetime')),
  event_type TEXT NOT NULL,
  target INTEGER NOT NULL DEFAULT 1,
  xp_reward INTEGER NOT NULL DEFAULT 0,
  coin_reward INTEGER NOT NULL DEFAULT 0,
  premium_only BOOLEAN NOT NULL DEFAULT FALSE,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(guild_id,quest_key)
);

CREATE TABLE IF NOT EXISTS member_quest_progress (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  quest_id BIGINT NOT NULL REFERENCES quest_definitions(id) ON DELETE CASCADE,
  period_key TEXT NOT NULL,
  progress INTEGER NOT NULL DEFAULT 0,
  completed_at TIMESTAMPTZ,
  rewarded_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id,quest_id,period_key)
);
CREATE INDEX IF NOT EXISTS quest_progress_member_idx
  ON member_quest_progress(guild_id,user_id,updated_at DESC);

CREATE TABLE IF NOT EXISTS achievement_definitions (
  guild_id TEXT NOT NULL,
  achievement_key TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  icon TEXT NOT NULL DEFAULT '🏅',
  xp_reward INTEGER NOT NULL DEFAULT 0,
  coin_reward INTEGER NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(guild_id,achievement_key)
);

CREATE TABLE IF NOT EXISTS store_items (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  item_key TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  emoji TEXT NOT NULL DEFAULT '🎁',
  cost_coins BIGINT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  stock INTEGER,
  per_user_limit INTEGER,
  fulfillment_type TEXT NOT NULL CHECK (fulfillment_type IN ('discord_premium','eafc_live','role','badge','custom')),
  duration_days INTEGER,
  role_id TEXT,
  billing_plan_slug TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(guild_id,item_key)
);

CREATE TABLE IF NOT EXISTS store_redemptions (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  store_item_id BIGINT REFERENCES store_items(id) ON DELETE SET NULL,
  item_key TEXT NOT NULL,
  item_name TEXT NOT NULL,
  cost_coins BIGINT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','FULFILLED','FAILED','REFUNDED','REJECTED')),
  claim_code TEXT NOT NULL,
  fulfillment_notes TEXT,
  fulfilled_by TEXT,
  fulfilled_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(guild_id,claim_code)
);
CREATE INDEX IF NOT EXISTS store_redemptions_queue_idx
  ON store_redemptions(guild_id,status,created_at DESC);

CREATE TABLE IF NOT EXISTS economy_event_queue (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PROCESSING','DONE','FAILED')),
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at TIMESTAMPTZ,
  UNIQUE(guild_id,event_type,source_type,source_id,user_id)
);
CREATE INDEX IF NOT EXISTS economy_event_queue_due_idx
  ON economy_event_queue(status,available_at,id);

-- Preserve XP already earned through the original community system.
INSERT INTO member_economy(guild_id,user_id,xp_total)
SELECT guild_id,user_id,COALESCE(xp,0) FROM member_stats
ON CONFLICT(guild_id,user_id) DO UPDATE
SET xp_total=GREATEST(member_economy.xp_total,EXCLUDED.xp_total),updated_at=now();

INSERT INTO economy_settings(guild_id)
SELECT guild_id FROM guild_settings
ON CONFLICT(guild_id) DO NOTHING;

INSERT INTO economy_seasons(guild_id,name,starts_at,ends_at)
SELECT g.guild_id,'FC27 Season 1',now(),now()+interval '30 days'
FROM guild_settings g
WHERE NOT EXISTS (SELECT 1 FROM economy_seasons s WHERE s.guild_id=g.guild_id AND s.active=TRUE);

INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'daily_chat','Warm up','Earn rewards from 10 qualifying messages.','daily','message',10,60,30,10 FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;
INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'daily_help','Help somebody','Have one message marked helpful.','daily','helpful_received',1,75,50,20 FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;
INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'daily_trade','Log a trade','Add one completed trade to your journal.','daily','trade_logged',1,50,25,30 FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;
INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'daily_checkin','Daily check-in','Claim today''s Live Coins.','daily','daily_claim',1,25,10,40 FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;
INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'weekly_active','Community regular','Earn rewards from 50 qualifying messages this week.','weekly','message',50,250,150,100 FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;
INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'weekly_help','Community MVP','Have five messages marked helpful this week.','weekly','helpful_received',5,350,250,110 FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;
INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'weekly_trader','Active trader','Log five completed trades this week.','weekly','trade_logged',5,250,150,120 FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;
INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'weekly_referral','Bring a mate','Generate one converted Premium referral this week.','weekly','referral_conversion',1,500,500,130 FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;
INSERT INTO quest_definitions(guild_id,quest_key,name,description,cadence,event_type,target,xp_reward,coin_reward,sort_order)
SELECT guild_id,'weekly_investor','Track the market','Join three community investments this week.','weekly','investment_join',3,100,75,140 FROM guild_settings ON CONFLICT(guild_id,quest_key) DO NOTHING;

INSERT INTO achievement_definitions(guild_id,achievement_key,name,description,icon,xp_reward,coin_reward,sort_order)
SELECT guild_id,'welcome_aboard','Welcome aboard','Joined the EAFC.Live community.','👋',25,25,10 FROM guild_settings ON CONFLICT(guild_id,achievement_key) DO NOTHING;
INSERT INTO achievement_definitions(guild_id,achievement_key,name,description,icon,xp_reward,coin_reward,sort_order)
SELECT guild_id,'level_5','Getting noticed','Reached level 5.','⚡',100,100,20 FROM guild_settings ON CONFLICT(guild_id,achievement_key) DO NOTHING;
INSERT INTO achievement_definitions(guild_id,achievement_key,name,description,icon,xp_reward,coin_reward,sort_order)
SELECT guild_id,'level_10','Market regular','Reached level 10.','📈',250,250,30 FROM guild_settings ON CONFLICT(guild_id,achievement_key) DO NOTHING;
INSERT INTO achievement_definitions(guild_id,achievement_key,name,description,icon,xp_reward,coin_reward,sort_order)
SELECT guild_id,'level_25','Community elite','Reached level 25.','👑',750,1000,40 FROM guild_settings ON CONFLICT(guild_id,achievement_key) DO NOTHING;
INSERT INTO achievement_definitions(guild_id,achievement_key,name,description,icon,xp_reward,coin_reward,sort_order)
SELECT guild_id,'streak_7','On a roll','Claimed rewards seven days running.','🔥',100,150,50 FROM guild_settings ON CONFLICT(guild_id,achievement_key) DO NOTHING;
INSERT INTO achievement_definitions(guild_id,achievement_key,name,description,icon,xp_reward,coin_reward,sort_order)
SELECT guild_id,'streak_30','Unstoppable','Claimed rewards thirty days running.','💎',500,750,60 FROM guild_settings ON CONFLICT(guild_id,achievement_key) DO NOTHING;
INSERT INTO achievement_definitions(guild_id,achievement_key,name,description,icon,xp_reward,coin_reward,sort_order)
SELECT guild_id,'helpful_10','Trusted helper','Had ten messages marked helpful.','💚',200,250,70 FROM guild_settings ON CONFLICT(guild_id,achievement_key) DO NOTHING;
INSERT INTO achievement_definitions(guild_id,achievement_key,name,description,icon,xp_reward,coin_reward,sort_order)
SELECT guild_id,'trader_10','Trader track record','Logged ten completed trades.','📊',200,250,80 FROM guild_settings ON CONFLICT(guild_id,achievement_key) DO NOTHING;

INSERT INTO store_items(guild_id,item_key,name,description,emoji,cost_coins,fulfillment_type,duration_days,billing_plan_slug,sort_order)
SELECT guild_id,'premium-7d','7 days Premium','Unlock the Premium Discord role and channels for 7 days.','💎',2000,'discord_premium',7,'premium-monthly',10 FROM guild_settings ON CONFLICT(guild_id,item_key) DO NOTHING;
INSERT INTO store_items(guild_id,item_key,name,description,emoji,cost_coins,fulfillment_type,duration_days,billing_plan_slug,sort_order)
SELECT guild_id,'premium-30d','1 month Premium','Unlock the Premium Discord role and channels for 30 days.','👑',6000,'discord_premium',30,'premium-monthly',20 FROM guild_settings ON CONFLICT(guild_id,item_key) DO NOTHING;
INSERT INTO store_items(guild_id,item_key,name,description,emoji,cost_coins,fulfillment_type,duration_days,metadata,sort_order)
SELECT guild_id,'eafclive-30d','1 month EAFC.Live','Redeem 30 days of EAFC.Live access. Staff fulfil this after account verification.','⚡',8000,'eafc_live',30,'{"requires_account_link":true}'::jsonb,30 FROM guild_settings ON CONFLICT(guild_id,item_key) DO NOTHING;

CREATE OR REPLACE FUNCTION queue_economy_reputation_event() RETURNS trigger AS $$
BEGIN
  INSERT INTO economy_event_queue(guild_id,user_id,event_type,source_type,source_id,metadata)
  VALUES(NEW.guild_id,NEW.receiver_id,'helpful_received','reputation_events',NEW.id::text,jsonb_build_object('giver_id',NEW.giver_id,'reason',NEW.reason))
  ON CONFLICT DO NOTHING;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS economy_reputation_event_trigger ON reputation_events;
CREATE TRIGGER economy_reputation_event_trigger AFTER INSERT ON reputation_events
FOR EACH ROW EXECUTE FUNCTION queue_economy_reputation_event();

CREATE OR REPLACE FUNCTION queue_economy_trade_event() RETURNS trigger AS $$
BEGIN
  IF NEW.status='CLOSED' THEN
    INSERT INTO economy_event_queue(guild_id,user_id,event_type,source_type,source_id,metadata)
    VALUES(NEW.guild_id,NEW.user_id,'trade_logged','trade_journal',NEW.id::text,jsonb_build_object('profit',COALESCE(NEW.profit,0),'player',NEW.player))
    ON CONFLICT DO NOTHING;
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS economy_trade_event_trigger ON trade_journal;
CREATE TRIGGER economy_trade_event_trigger AFTER INSERT ON trade_journal
FOR EACH ROW EXECUTE FUNCTION queue_economy_trade_event();

CREATE OR REPLACE FUNCTION queue_economy_investment_event() RETURNS trigger AS $$
DECLARE g TEXT;
BEGIN
  SELECT guild_id INTO g FROM investments WHERE id=NEW.investment_id;
  IF g IS NOT NULL THEN
    INSERT INTO economy_event_queue(guild_id,user_id,event_type,source_type,source_id)
    VALUES(g,NEW.user_id,'investment_join','investment_entries',NEW.investment_id::text)
    ON CONFLICT DO NOTHING;
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS economy_investment_event_trigger ON investment_entries;
CREATE TRIGGER economy_investment_event_trigger AFTER INSERT ON investment_entries
FOR EACH ROW EXECUTE FUNCTION queue_economy_investment_event();
