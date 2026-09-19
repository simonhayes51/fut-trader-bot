-- EAFC.Live Community Suite v5
-- Discord-first onboarding, safety, recognition, growth, analytics and retention.

ALTER TABLE reputation_events ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'Community';
ALTER TABLE reputation_events ADD COLUMN IF NOT EXISTS comment TEXT;
CREATE INDEX IF NOT EXISTS reputation_events_period_idx ON reputation_events(guild_id,created_at DESC,category);

ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS min_member_days INTEGER NOT NULL DEFAULT 0;
ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS min_level INTEGER NOT NULL DEFAULT 0;
ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS verified_only BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS blacklist_user_ids TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS blacklist_role_ids TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS bonus_rules JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS reroll_exclude_previous BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE store_items ADD COLUMN IF NOT EXISTS available_from TIMESTAMPTZ;
ALTER TABLE store_items ADD COLUMN IF NOT EXISTS available_until TIMESTAMPTZ;
ALTER TABLE store_items ADD COLUMN IF NOT EXISTS season_id BIGINT REFERENCES economy_seasons(id) ON DELETE SET NULL;
ALTER TABLE store_items ADD COLUMN IF NOT EXISTS cosmetic BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE member_stats ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE member_stats ADD COLUMN IF NOT EXISTS first_active_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS member_profiles (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  birthday_day INTEGER CHECK (birthday_day BETWEEN 1 AND 31),
  birthday_month INTEGER CHECK (birthday_month BETWEEN 1 AND 12),
  platform TEXT,
  timezone TEXT,
  interests TEXT[] NOT NULL DEFAULT '{}',
  profile_title TEXT,
  accent TEXT,
  featured_achievements TEXT[] NOT NULL DEFAULT '{}',
  birthday_public BOOLEAN NOT NULL DEFAULT TRUE,
  notification_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id)
);

CREATE TABLE IF NOT EXISTS onboarding_configs (
  guild_id TEXT PRIMARY KEY,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  channel_id TEXT,
  verified_role_id TEXT,
  quarantine_role_id TEXT,
  platform_roles JSONB NOT NULL DEFAULT '{}'::jsonb,
  interest_roles JSONB NOT NULL DEFAULT '{}'::jsonb,
  notification_roles JSONB NOT NULL DEFAULT '{}'::jsonb,
  min_account_age_hours INTEGER NOT NULL DEFAULT 24,
  panel_message_id TEXT,
  welcome_title TEXT NOT NULL DEFAULT 'Welcome to EAFC.Live',
  welcome_body TEXT NOT NULL DEFAULT 'Verify your account, choose your platform and personalise your community experience.',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS onboarding_answers (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  verified BOOLEAN NOT NULL DEFAULT FALSE,
  platform TEXT,
  interests TEXT[] NOT NULL DEFAULT '{}',
  notification_roles TEXT[] NOT NULL DEFAULT '{}',
  completed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id)
);

CREATE TABLE IF NOT EXISTS member_funnel (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  joined_at TIMESTAMPTZ,
  verified_at TIMESTAMPTZ,
  roles_selected_at TIMESTAMPTZ,
  first_active_at TIMESTAMPTZ,
  retained_1d BOOLEAN NOT NULL DEFAULT FALSE,
  retained_7d BOOLEAN NOT NULL DEFAULT FALSE,
  retained_30d BOOLEAN NOT NULL DEFAULT FALSE,
  left_at TIMESTAMPTZ,
  inviter_id TEXT,
  invite_code TEXT,
  PRIMARY KEY(guild_id,user_id)
);
CREATE INDEX IF NOT EXISTS member_funnel_joined_idx ON member_funnel(guild_id,joined_at DESC);

CREATE TABLE IF NOT EXISTS member_afk (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  reason TEXT,
  set_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id)
);

CREATE TABLE IF NOT EXISTS birthday_awards (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  award_year INTEGER NOT NULL,
  awarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id,award_year)
);

CREATE TABLE IF NOT EXISTS counting_configs (
  guild_id TEXT PRIMARY KEY,
  channel_id TEXT,
  next_number BIGINT NOT NULL DEFAULT 1,
  last_user_id TEXT,
  last_message_id TEXT,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  reward_every INTEGER NOT NULL DEFAULT 100,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS server_counters (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  metric TEXT NOT NULL CHECK (metric IN ('members','online','premium','boosters','verified')),
  label TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(guild_id,channel_id)
);

CREATE TABLE IF NOT EXISTS security_events (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor_id TEXT,
  target_id TEXT,
  severity TEXT NOT NULL DEFAULT 'info',
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_taken TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS security_events_recent_idx ON security_events(guild_id,created_at DESC);

CREATE TABLE IF NOT EXISTS staff_action_windows (
  guild_id TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  window_started_at TIMESTAMPTZ NOT NULL,
  action_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(guild_id,actor_id,action_type)
);

CREATE TABLE IF NOT EXISTS message_templates (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  name TEXT NOT NULL,
  template_type TEXT NOT NULL DEFAULT 'announcement',
  title TEXT,
  body TEXT NOT NULL,
  colour INTEGER,
  image_url TEXT,
  thumbnail_url TEXT,
  mention_role_id TEXT,
  button_config JSONB NOT NULL DEFAULT '[]'::jsonb,
  select_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  saved BOOLEAN NOT NULL DEFAULT TRUE,
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS published_messages (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  template_id BIGINT REFERENCES message_templates(id) ON DELETE SET NULL,
  channel_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  purpose TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role_panels (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  name TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  message_id TEXT,
  panel_type TEXT NOT NULL DEFAULT 'buttons',
  roles JSONB NOT NULL DEFAULT '[]'::jsonb,
  title TEXT NOT NULL,
  body TEXT,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reaction_roles (
  guild_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  emoji TEXT NOT NULL,
  role_id TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY(guild_id,message_id,emoji)
);

CREATE TABLE IF NOT EXISTS level_workflows (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  level INTEGER NOT NULL,
  role_id TEXT,
  coin_reward INTEGER NOT NULL DEFAULT 0,
  message TEXT,
  announce_channel_id TEXT,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE(guild_id,level)
);

CREATE TABLE IF NOT EXISTS level_workflow_awards (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  workflow_id BIGINT NOT NULL REFERENCES level_workflows(id) ON DELETE CASCADE,
  awarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id,workflow_id)
);

CREATE TABLE IF NOT EXISTS kudos_milestones (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  milestone INTEGER NOT NULL,
  role_id TEXT,
  xp_reward INTEGER NOT NULL DEFAULT 0,
  coin_reward INTEGER NOT NULL DEFAULT 0,
  badge_key TEXT,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE(guild_id,milestone)
);

CREATE TABLE IF NOT EXISTS kudos_awards (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  milestone_id BIGINT NOT NULL REFERENCES kudos_milestones(id) ON DELETE CASCADE,
  awarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id,milestone_id)
);

CREATE TABLE IF NOT EXISTS recap_settings (
  guild_id TEXT PRIMARY KEY,
  weekly_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  weekly_channel_id TEXT,
  weekly_day INTEGER NOT NULL DEFAULT 0,
  weekly_hour INTEGER NOT NULL DEFAULT 19,
  personal_weekly_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  monthly_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  monthly_channel_id TEXT,
  last_weekly_key TEXT,
  last_monthly_key TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recognition_role_settings (
  guild_id TEXT PRIMARY KEY,
  weekly_role_id TEXT,
  season_role_id TEXT,
  current_weekly_user_id TEXT,
  current_season_user_id TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invite_snapshots (
  guild_id TEXT NOT NULL,
  code TEXT NOT NULL,
  inviter_id TEXT,
  uses INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,code)
);

CREATE TABLE IF NOT EXISTS invite_joins (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  inviter_id TEXT,
  invite_code TEXT,
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  retained_7d BOOLEAN NOT NULL DEFAULT FALSE,
  rewarded BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY(guild_id,user_id)
);
CREATE INDEX IF NOT EXISTS invite_joins_inviter_idx ON invite_joins(guild_id,inviter_id,joined_at DESC);

CREATE TABLE IF NOT EXISTS invite_milestones (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  retained_invites INTEGER NOT NULL,
  role_id TEXT,
  xp_reward INTEGER NOT NULL DEFAULT 0,
  coin_reward INTEGER NOT NULL DEFAULT 0,
  premium_days INTEGER NOT NULL DEFAULT 0,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE(guild_id,retained_invites)
);

CREATE TABLE IF NOT EXISTS invite_milestone_awards (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  milestone_id BIGINT NOT NULL REFERENCES invite_milestones(id) ON DELETE CASCADE,
  awarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id,milestone_id)
);

CREATE TABLE IF NOT EXISTS partnerships (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  partner_name TEXT NOT NULL,
  server_id TEXT,
  contact_name TEXT,
  contact_discord_id TEXT,
  invite_code TEXT,
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  started_at DATE,
  review_at DATE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usage_events (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  user_id TEXT,
  event_type TEXT NOT NULL,
  feature_key TEXT,
  channel_id TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS usage_events_feature_idx ON usage_events(guild_id,feature_key,created_at DESC);
CREATE INDEX IF NOT EXISTS usage_events_type_idx ON usage_events(guild_id,event_type,created_at DESC);

CREATE TABLE IF NOT EXISTS dashboard_widgets (
  guild_id TEXT NOT NULL,
  admin_user_id TEXT NOT NULL,
  widget_key TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(guild_id,admin_user_id,widget_key)
);

CREATE TABLE IF NOT EXISTS booster_milestones (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  months INTEGER NOT NULL,
  role_id TEXT,
  xp_reward INTEGER NOT NULL DEFAULT 0,
  coin_reward INTEGER NOT NULL DEFAULT 0,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE(guild_id,months)
);

CREATE TABLE IF NOT EXISTS booster_awards (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  milestone_id BIGINT NOT NULL REFERENCES booster_milestones(id) ON DELETE CASCADE,
  awarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id,milestone_id)
);

CREATE TABLE IF NOT EXISTS flash_drops (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  message_id TEXT,
  name TEXT NOT NULL,
  reward_coins INTEGER NOT NULL DEFAULT 0,
  reward_xp INTEGER NOT NULL DEFAULT 0,
  max_claims INTEGER,
  starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ends_at TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL DEFAULT 'LIVE',
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS flash_drop_claims (
  drop_id BIGINT NOT NULL REFERENCES flash_drops(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL,
  claimed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(drop_id,user_id)
);

CREATE TABLE IF NOT EXISTS health_findings (
  id BIGSERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  finding_key TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  fix_type TEXT,
  fix_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ,
  UNIQUE(guild_id,finding_key)
);

CREATE TABLE IF NOT EXISTS temporary_role_grants (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role_id TEXT NOT NULL,
  source TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id,role_id,source,source_ref)
);
CREATE INDEX IF NOT EXISTS temporary_role_grants_due_idx ON temporary_role_grants(expires_at) WHERE expires_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS profile_cosmetics (
  guild_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  cosmetic_key TEXT NOT NULL,
  value TEXT,
  source TEXT,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(guild_id,user_id,cosmetic_key)
);

INSERT INTO onboarding_configs(guild_id) SELECT guild_id FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO recap_settings(guild_id) SELECT guild_id FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO recognition_role_settings(guild_id) SELECT guild_id FROM guild_settings ON CONFLICT DO NOTHING;

INSERT INTO kudos_milestones(guild_id,milestone,xp_reward,coin_reward,badge_key)
SELECT guild_id,10,100,100,'kudos_10' FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO kudos_milestones(guild_id,milestone,xp_reward,coin_reward,badge_key)
SELECT guild_id,25,200,250,'kudos_25' FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO kudos_milestones(guild_id,milestone,xp_reward,coin_reward,badge_key)
SELECT guild_id,50,350,500,'kudos_50' FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO kudos_milestones(guild_id,milestone,xp_reward,coin_reward,badge_key)
SELECT guild_id,100,750,1000,'kudos_100' FROM guild_settings ON CONFLICT DO NOTHING;

INSERT INTO invite_milestones(guild_id,retained_invites,xp_reward,coin_reward)
SELECT guild_id,3,250,250 FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO invite_milestones(guild_id,retained_invites,xp_reward,coin_reward)
SELECT guild_id,5,500,500 FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO invite_milestones(guild_id,retained_invites,xp_reward,coin_reward)
SELECT guild_id,10,1000,1000 FROM guild_settings ON CONFLICT DO NOTHING;

INSERT INTO booster_milestones(guild_id,months,xp_reward,coin_reward)
SELECT guild_id,1,100,150 FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO booster_milestones(guild_id,months,xp_reward,coin_reward)
SELECT guild_id,3,250,350 FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO booster_milestones(guild_id,months,xp_reward,coin_reward)
SELECT guild_id,6,500,750 FROM guild_settings ON CONFLICT DO NOTHING;
INSERT INTO booster_milestones(guild_id,months,xp_reward,coin_reward)
SELECT guild_id,12,1000,1500 FROM guild_settings ON CONFLICT DO NOTHING;
