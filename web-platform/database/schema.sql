-- FUT Hub Platform Database Schema
-- PostgreSQL Schema

-- ============================================
-- USERS & AUTHENTICATION
-- ============================================

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    discord_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) NOT NULL,
    discriminator VARCHAR(10),
    avatar_url TEXT,
    email VARCHAR(255),
    is_trader BOOLEAN DEFAULT FALSE,
    is_verified_trader BOOLEAN DEFAULT FALSE,
    is_premium BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,

    -- User stats
    reputation_score INTEGER DEFAULT 0,
    total_reviews_given INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0,

    CONSTRAINT unique_discord_id UNIQUE (discord_id)
);

CREATE INDEX idx_users_discord_id ON users(discord_id);
CREATE INDEX idx_users_is_trader ON users(is_trader);

-- ============================================
-- TRADER PROFILES
-- ============================================

CREATE TABLE trader_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,

    -- Profile info
    display_name VARCHAR(255) NOT NULL,
    bio TEXT,
    specialties TEXT[], -- ['Icons', 'Fodder', 'Meta Cards']

    -- Pricing
    subscription_price_monthly DECIMAL(10,2), -- e.g., 9.99
    subscription_price_vip DECIMAL(10,2), -- optional VIP tier
    is_accepting_subscribers BOOLEAN DEFAULT TRUE,

    -- Stats (auto-calculated)
    total_signals INTEGER DEFAULT 0,
    winning_signals INTEGER DEFAULT 0,
    losing_signals INTEGER DEFAULT 0,
    active_signals INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2) DEFAULT 0.00, -- percentage
    avg_roi DECIMAL(5,2) DEFAULT 0.00, -- percentage

    -- Ratings (auto-calculated from reviews)
    avg_rating DECIMAL(3,2) DEFAULT 0.00, -- 0.00 to 5.00
    total_reviews INTEGER DEFAULT 0,

    -- Earnings
    total_subscribers INTEGER DEFAULT 0,
    total_earnings DECIMAL(10,2) DEFAULT 0.00,

    -- Social links
    twitter_handle VARCHAR(255),
    twitch_handle VARCHAR(255),
    youtube_url TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_trader_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_trader_user_id ON trader_profiles(user_id);
CREATE INDEX idx_trader_win_rate ON trader_profiles(win_rate DESC);
CREATE INDEX idx_trader_rating ON trader_profiles(avg_rating DESC);

-- ============================================
-- SUBSCRIPTIONS
-- ============================================

CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    trader_id INTEGER REFERENCES trader_profiles(id) ON DELETE CASCADE,

    tier VARCHAR(50) DEFAULT 'standard', -- 'standard' or 'vip'
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'cancelled', 'expired'

    -- Stripe info
    stripe_subscription_id VARCHAR(255) UNIQUE,
    stripe_customer_id VARCHAR(255),

    -- Dates
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    cancelled_at TIMESTAMP,

    CONSTRAINT unique_user_trader_subscription UNIQUE (user_id, trader_id)
);

CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_trader_id ON subscriptions(trader_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- ============================================
-- TRADING SIGNALS
-- ============================================

CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    trader_id INTEGER REFERENCES trader_profiles(id) ON DELETE CASCADE,

    -- Signal details
    card_name VARCHAR(255) NOT NULL,
    card_rating INTEGER,
    card_position VARCHAR(10),
    player_image TEXT, -- URL to player card image
    card_type VARCHAR(50), -- 'Gold', 'TOTW', 'Icon', 'Hero', etc.
    trade_type VARCHAR(50), -- 'flip', 'risky', 'investment', 'safe_bet', 'snipe'

    signal_type VARCHAR(50) NOT NULL, -- 'BUY', 'SELL', 'HOLD', 'AVOID'
    is_premium BOOLEAN DEFAULT FALSE, -- premium = subscribers only

    -- Entry
    entry_price_min INTEGER,
    entry_price_max INTEGER,
    entry_posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Exit
    exit_price INTEGER,
    exit_posted_at TIMESTAMP,

    -- Targets
    target_price INTEGER,
    stop_loss_price INTEGER,
    time_frame VARCHAR(50), -- 'Quick flip', '3-5 days', 'Long term'

    -- Analysis
    risk_level VARCHAR(50), -- 'Low', 'Medium', 'High'
    confidence_level INTEGER, -- 1-100
    reasoning TEXT,

    -- Results (auto-calculated when exit posted)
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'closed', 'expired'
    result VARCHAR(50), -- 'win', 'loss', 'neutral'
    roi DECIMAL(5,2), -- percentage profit/loss

    -- Engagement
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    invested_count INTEGER DEFAULT 0, -- how many users clicked "I invested"

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_signals_trader_id ON signals(trader_id);
CREATE INDEX idx_signals_status ON signals(status);
CREATE INDEX idx_signals_is_premium ON signals(is_premium);
CREATE INDEX idx_signals_created_at ON signals(created_at DESC);
CREATE INDEX idx_signals_card_type ON signals(card_type);
CREATE INDEX idx_signals_trade_type ON signals(trade_type);

-- ============================================
-- CONTENT (One-off products)
-- ============================================

CREATE TABLE content (
    id SERIAL PRIMARY KEY,
    trader_id INTEGER REFERENCES trader_profiles(id) ON DELETE CASCADE,

    -- Content details
    title VARCHAR(255) NOT NULL,
    description TEXT,
    content_type VARCHAR(50) NOT NULL, -- 'guide', 'course', 'template', 'consultation'

    -- Pricing
    price DECIMAL(10,2) NOT NULL,

    -- Files
    file_url TEXT, -- S3/storage URL
    file_type VARCHAR(50), -- 'pdf', 'video', 'excel', 'zip'
    file_size_mb DECIMAL(10,2),

    -- Preview
    preview_text TEXT,
    preview_image_url TEXT,

    -- Stats
    total_sales INTEGER DEFAULT 0,
    total_revenue DECIMAL(10,2) DEFAULT 0.00,

    -- Ratings
    avg_rating DECIMAL(3,2) DEFAULT 0.00,
    total_reviews INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_content_trader_id ON content(trader_id);
CREATE INDEX idx_content_rating ON content(avg_rating DESC);

-- ============================================
-- PURCHASES (One-off content)
-- ============================================

CREATE TABLE purchases (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    content_id INTEGER REFERENCES content(id) ON DELETE CASCADE,

    price_paid DECIMAL(10,2) NOT NULL,
    stripe_payment_id VARCHAR(255),

    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_user_content_purchase UNIQUE (user_id, content_id)
);

CREATE INDEX idx_purchases_user_id ON purchases(user_id);
CREATE INDEX idx_purchases_content_id ON purchases(content_id);

-- ============================================
-- REVIEWS & RATINGS
-- ============================================

CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,

    -- What is being reviewed (polymorphic)
    reviewable_type VARCHAR(50) NOT NULL, -- 'trader', 'content', 'signal'
    reviewable_id INTEGER NOT NULL,

    -- Review content
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    review_text TEXT,

    -- Engagement
    helpful_count INTEGER DEFAULT 0,
    unhelpful_count INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_user_review UNIQUE (user_id, reviewable_type, reviewable_id)
);

CREATE INDEX idx_reviews_user_id ON reviews(user_id);
CREATE INDEX idx_reviews_reviewable ON reviews(reviewable_type, reviewable_id);
CREATE INDEX idx_reviews_rating ON reviews(rating DESC);

-- ============================================
-- COMMENTS (Nested, threaded)
-- ============================================

CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,

    -- What is being commented on (polymorphic)
    commentable_type VARCHAR(50) NOT NULL, -- 'signal', 'content', 'guide', 'trader'
    commentable_id INTEGER NOT NULL,

    -- Comment content
    comment_text TEXT NOT NULL,

    -- Threading (nested comments)
    parent_comment_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,

    -- Voting
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,

    -- Flags
    is_edited BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE, -- traders can pin important comments

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_comments_user_id ON comments(user_id);
CREATE INDEX idx_comments_commentable ON comments(commentable_type, commentable_id);
CREATE INDEX idx_comments_parent ON comments(parent_comment_id);
CREATE INDEX idx_comments_created_at ON comments(created_at DESC);

-- ============================================
-- VOTES (Unified voting system)
-- ============================================

CREATE TABLE votes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,

    -- What is being voted on (polymorphic)
    votable_type VARCHAR(50) NOT NULL, -- 'comment', 'review', 'guide'
    votable_id INTEGER NOT NULL,

    vote_type VARCHAR(10) NOT NULL, -- 'upvote', 'downvote', 'helpful', 'unhelpful'

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_user_vote UNIQUE (user_id, votable_type, votable_id)
);

CREATE INDEX idx_votes_user_id ON votes(user_id);
CREATE INDEX idx_votes_votable ON votes(votable_type, votable_id);

-- ============================================
-- COMMUNITY CONTENT (User guides, tactics, etc.)
-- ============================================

CREATE TABLE community_content (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,

    -- Content details
    title VARCHAR(255) NOT NULL,
    content_type VARCHAR(50) NOT NULL, -- 'guide', 'tactic', 'review', 'tip'
    content_text TEXT,

    -- Media
    image_urls TEXT[], -- array of image URLs
    video_url TEXT,

    -- Tags
    tags TEXT[], -- ['icons', 'trading', 'meta']
    category VARCHAR(50), -- 'trading', 'gameplay', 'squad-building'

    -- Engagement
    views INTEGER DEFAULT 0,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,

    -- Ratings
    avg_rating DECIMAL(3,2) DEFAULT 0.00,
    total_ratings INTEGER DEFAULT 0,

    -- Moderation
    is_featured BOOLEAN DEFAULT FALSE,
    is_approved BOOLEAN DEFAULT TRUE,
    is_flagged BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_community_content_user_id ON community_content(user_id);
CREATE INDEX idx_community_content_type ON community_content(content_type);
CREATE INDEX idx_community_content_category ON community_content(category);
CREATE INDEX idx_community_content_upvotes ON community_content(upvotes DESC);

-- ============================================
-- DISCORD SERVERS
-- ============================================

CREATE TABLE discord_servers (
    id SERIAL PRIMARY KEY,
    submitted_by INTEGER REFERENCES users(id),

    -- Server info
    server_name VARCHAR(255) NOT NULL,
    invite_link TEXT NOT NULL,
    server_icon_url TEXT,

    -- Details
    description TEXT,
    member_count INTEGER,
    focus VARCHAR(100), -- 'Trading', 'Competitive', 'Casual'
    is_premium_server BOOLEAN DEFAULT FALSE,
    premium_price DECIMAL(10,2),

    -- Featured traders on this server
    featured_trader_ids INTEGER[], -- array of trader_profile.id

    -- Stats
    clicks INTEGER DEFAULT 0,
    joins_tracked INTEGER DEFAULT 0,

    -- Ratings
    avg_rating DECIMAL(3,2) DEFAULT 0.00,
    total_reviews INTEGER DEFAULT 0,

    -- Moderation
    is_approved BOOLEAN DEFAULT FALSE,
    is_featured BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_discord_servers_submitted_by ON discord_servers(submitted_by);
CREATE INDEX idx_discord_servers_approved ON discord_servers(is_approved);

-- ============================================
-- PRICE DATA (Scraped from Futbin)
-- ============================================

CREATE TABLE price_data (
    id SERIAL PRIMARY KEY,

    -- Card identification
    card_name VARCHAR(255) NOT NULL,
    card_rating INTEGER,
    card_version VARCHAR(50), -- 'Gold', 'IF', 'Icon', etc.
    futbin_id INTEGER,

    -- Prices
    ps_price INTEGER,
    xbox_price INTEGER,
    pc_price INTEGER,

    -- Changes
    ps_24h_change DECIMAL(5,2),
    xbox_24h_change DECIMAL(5,2),
    pc_24h_change DECIMAL(5,2),

    -- Timestamp
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_card_timestamp UNIQUE (card_name, card_rating, scraped_at)
);

CREATE INDEX idx_price_data_card ON price_data(card_name, card_rating);
CREATE INDEX idx_price_data_scraped_at ON price_data(scraped_at DESC);

-- ============================================
-- USER INTERACTIONS (Track engagement)
-- ============================================

CREATE TABLE user_interactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    signal_id INTEGER REFERENCES signals(id) ON DELETE CASCADE,

    interaction_type VARCHAR(50) NOT NULL, -- 'viewed', 'liked', 'invested', 'not_for_me'

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_user_signal_interaction UNIQUE (user_id, signal_id, interaction_type)
);

CREATE INDEX idx_interactions_user_id ON user_interactions(user_id);
CREATE INDEX idx_interactions_signal_id ON user_interactions(signal_id);

-- ============================================
-- NOTIFICATIONS
-- ============================================

CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,

    -- Notification details
    notification_type VARCHAR(50) NOT NULL, -- 'new_signal', 'signal_exit', 'new_comment', 'new_review'
    title VARCHAR(255) NOT NULL,
    message TEXT,

    -- Link
    link_url TEXT,

    -- Status
    is_read BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);

-- ============================================
-- ANALYTICS / METRICS
-- ============================================

CREATE TABLE analytics_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    event_type VARCHAR(100) NOT NULL, -- 'page_view', 'signal_view', 'subscription_created'
    event_data JSONB, -- flexible JSON data

    -- Context
    ip_address INET,
    user_agent TEXT,
    referrer TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analytics_user_id ON analytics_events(user_id);
CREATE INDEX idx_analytics_event_type ON analytics_events(event_type);
CREATE INDEX idx_analytics_created_at ON analytics_events(created_at DESC);

-- ============================================
-- FUNCTIONS & TRIGGERS
-- ============================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to relevant tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_trader_profiles_updated_at BEFORE UPDATE ON trader_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_signals_updated_at BEFORE UPDATE ON signals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_content_updated_at BEFORE UPDATE ON content FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to calculate trader win rate
CREATE OR REPLACE FUNCTION calculate_trader_win_rate(trader_profile_id INTEGER)
RETURNS VOID AS $$
DECLARE
    total_closed INTEGER;
    total_wins INTEGER;
    calculated_win_rate DECIMAL(5,2);
BEGIN
    SELECT COUNT(*) INTO total_closed
    FROM signals
    WHERE trader_id = trader_profile_id AND status = 'closed';

    SELECT COUNT(*) INTO total_wins
    FROM signals
    WHERE trader_id = trader_profile_id AND status = 'closed' AND result = 'win';

    IF total_closed > 0 THEN
        calculated_win_rate := (total_wins::DECIMAL / total_closed::DECIMAL) * 100;
    ELSE
        calculated_win_rate := 0;
    END IF;

    UPDATE trader_profiles
    SET
        total_signals = total_closed,
        winning_signals = total_wins,
        losing_signals = total_closed - total_wins,
        win_rate = calculated_win_rate
    WHERE id = trader_profile_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- SEED DATA (Optional - for testing)
-- ============================================

-- Insert example user
INSERT INTO users (discord_id, username, avatar_url, is_trader)
VALUES ('123456789', 'TestTrader', 'https://cdn.discordapp.com/avatars/123/abc.png', TRUE);

-- Insert example trader profile
INSERT INTO trader_profiles (user_id, display_name, bio, subscription_price_monthly, specialties)
VALUES (
    1,
    'FUTWolf',
    'Icon trading specialist. 5 years experience. Focus on weekend flips.',
    9.99,
    ARRAY['Icons', 'Meta Cards', 'Weekend Flips']
);
