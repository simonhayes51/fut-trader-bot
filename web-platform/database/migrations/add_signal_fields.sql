-- Migration: Add player_image, card_type, and trade_type to signals table
-- Date: 2026-01-10

ALTER TABLE signals
ADD COLUMN player_image TEXT,
ADD COLUMN card_type VARCHAR(50), -- 'Gold', 'TOTW', 'Icon', 'Hero', 'Special', etc.
ADD COLUMN trade_type VARCHAR(50); -- 'flip', 'risky', 'investment', 'safe_bet', 'snipe'

-- Add indexes for filtering
CREATE INDEX idx_signals_card_type ON signals(card_type);
CREATE INDEX idx_signals_trade_type ON signals(trade_type);

-- Update existing signals with default values (optional)
UPDATE signals SET card_type = 'Gold' WHERE card_type IS NULL;
UPDATE signals SET trade_type = 'flip' WHERE trade_type IS NULL;
