const express = require('express');
const router = express.Router();
const { query, transaction } = require('../db');
const { body, param, validationResult } = require('express-validator');

// ============================================
// MIDDLEWARE
// ============================================

const requireAuth = (req, res, next) => {
  req.user = { id: 1 };
  next();
};

const requireTrader = async (req, res, next) => {
  const result = await query(
    'SELECT id FROM trader_profiles WHERE user_id = $1',
    [req.user.id]
  );

  if (result.rows.length === 0) {
    return res.status(403).json({ error: 'Trader profile required' });
  }

  req.traderId = result.rows[0].id;
  next();
};

// ============================================
// BROWSE SIGNALS
// ============================================

router.get('/',
  async (req, res) => {
    try {
      const {
        status = 'active',
        is_premium,
        trader_id,
        sort = 'recent',
        limit = 20,
        offset = 0
      } = req.query;
      const userId = req.user?.id;

      // Build WHERE clause
      let whereConditions = [];
      const queryParams = [];
      let paramIndex = 1;

      if (status !== 'all') {
        queryParams.push(status);
        whereConditions.push(`s.status = $${paramIndex}`);
        paramIndex++;
      }

      if (is_premium !== undefined) {
        queryParams.push(is_premium === 'true');
        whereConditions.push(`s.is_premium = $${paramIndex}`);
        paramIndex++;
      }

      if (trader_id) {
        queryParams.push(parseInt(trader_id));
        whereConditions.push(`s.trader_id = $${paramIndex}`);
        paramIndex++;
      }

      // Sort options
      let orderBy = 's.created_at DESC'; // recent
      if (sort === 'popular') orderBy = 's.invested_count DESC, s.likes DESC';
      if (sort === 'roi') orderBy = 's.roi DESC NULLS LAST';

      const whereClause = whereConditions.length > 0
        ? `WHERE ${whereConditions.join(' AND ')}`
        : '';

      queryParams.push(limit, offset);

      const result = await query(`
        SELECT
          s.*,
          tp.display_name as trader_name,
          tp.avg_rating as trader_rating,
          u.avatar_url as trader_avatar,
          (SELECT COUNT(*) FROM comments WHERE commentable_type = 'signal' AND commentable_id = s.id) as comment_count,
          CASE
            WHEN $${paramIndex + 1}::INTEGER IS NOT NULL THEN
              (SELECT interaction_type FROM user_interactions
               WHERE user_id = $${paramIndex + 1} AND signal_id = s.id AND interaction_type = 'invested')
            ELSE NULL
          END as user_invested
        FROM signals s
        JOIN trader_profiles tp ON tp.id = s.trader_id
        JOIN users u ON u.id = tp.user_id
        ${whereClause}
        ORDER BY ${orderBy}
        LIMIT $${paramIndex} OFFSET $${paramIndex + 1}
      `, [...queryParams, userId]);

      res.json({ signals: result.rows });

    } catch (error) {
      console.error('Browse signals error:', error);
      res.status(500).json({ error: 'Failed to fetch signals' });
    }
  }
);

// ============================================
// GET SIGNAL DETAILS
// ============================================

router.get('/:id',
  param('id').isInt(),
  async (req, res) => {
    try {
      const { id } = req.params;
      const userId = req.user?.id;

      // Get signal with trader info
      const result = await query(`
        SELECT
          s.*,
          tp.id as trader_id,
          tp.display_name as trader_name,
          tp.avg_rating as trader_rating,
          tp.win_rate as trader_win_rate,
          u.avatar_url as trader_avatar,
          u.is_verified_trader,
          CASE
            WHEN $2::INTEGER IS NOT NULL THEN
              (SELECT TRUE FROM subscriptions
               WHERE user_id = $2 AND trader_id = tp.id AND status = 'active')
            ELSE FALSE
          END as user_is_subscribed,
          CASE
            WHEN $2::INTEGER IS NOT NULL THEN
              (SELECT interaction_type FROM user_interactions
               WHERE user_id = $2 AND signal_id = s.id AND interaction_type = 'invested')
            ELSE NULL
          END as user_invested
        FROM signals s
        JOIN trader_profiles tp ON tp.id = s.trader_id
        JOIN users u ON u.id = tp.user_id
        WHERE s.id = $1
      `, [id, userId]);

      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Signal not found' });
      }

      const signal = result.rows[0];

      // Check if premium and not subscribed
      if (signal.is_premium && !signal.user_is_subscribed) {
        // Return limited info
        return res.json({
          signal: {
            id: signal.id,
            trader_id: signal.trader_id,
            trader_name: signal.trader_name,
            card_name: signal.card_name,
            signal_type: signal.signal_type,
            is_premium: true,
            created_at: signal.created_at,
            message: 'Subscribe to view full signal details'
          }
        });
      }

      // Increment view count
      await query('UPDATE signals SET views = views + 1 WHERE id = $1', [id]);

      res.json({ signal });

    } catch (error) {
      console.error('Get signal error:', error);
      res.status(500).json({ error: 'Failed to fetch signal' });
    }
  }
);

// ============================================
// CREATE SIGNAL
// ============================================

router.post('/',
  requireAuth,
  requireTrader,
  body('cardName').isString().isLength({ min: 2, max: 255 }),
  body('cardRating').optional().isInt({ min: 40, max: 99 }),
  body('cardPosition').optional().isString(),
  body('signalType').isIn(['BUY', 'SELL', 'HOLD', 'AVOID']),
  body('isPremium').isBoolean(),
  body('entryPriceMin').optional().isInt({ min: 0 }),
  body('entryPriceMax').optional().isInt({ min: 0 }),
  body('targetPrice').optional().isInt({ min: 0 }),
  body('stopLossPrice').optional().isInt({ min: 0 }),
  body('timeFrame').optional().isString(),
  body('riskLevel').isIn(['Low', 'Medium', 'High']),
  body('confidenceLevel').optional().isInt({ min: 0, max: 100 }),
  body('reasoning').optional().isString().isLength({ max: 2000 }),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const {
        cardName,
        cardRating,
        cardPosition,
        signalType,
        isPremium,
        entryPriceMin,
        entryPriceMax,
        targetPrice,
        stopLossPrice,
        timeFrame,
        riskLevel,
        confidenceLevel,
        reasoning
      } = req.body;

      const traderId = req.traderId;

      const result = await query(`
        INSERT INTO signals (
          trader_id, card_name, card_rating, card_position, signal_type,
          is_premium, entry_price_min, entry_price_max, target_price,
          stop_loss_price, time_frame, risk_level, confidence_level, reasoning
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING *
      `, [
        traderId, cardName, cardRating, cardPosition, signalType,
        isPremium, entryPriceMin, entryPriceMax, targetPrice,
        stopLossPrice, timeFrame, riskLevel, confidenceLevel, reasoning
      ]);

      res.status(201).json({
        message: 'Signal created successfully',
        signal: result.rows[0]
      });

    } catch (error) {
      console.error('Create signal error:', error);
      res.status(500).json({ error: 'Failed to create signal' });
    }
  }
);

// ============================================
// UPDATE SIGNAL
// ============================================

router.put('/:id',
  requireAuth,
  requireTrader,
  param('id').isInt(),
  async (req, res) => {
    try {
      const { id } = req.params;
      const traderId = req.traderId;

      // Verify ownership
      const checkResult = await query(
        'SELECT id FROM signals WHERE id = $1 AND trader_id = $2',
        [id, traderId]
      );

      if (checkResult.rows.length === 0) {
        return res.status(404).json({ error: 'Signal not found or unauthorized' });
      }

      // Build UPDATE query
      const updates = [];
      const values = [];
      let paramIndex = 1;

      const allowedFields = [
        'reasoning', 'targetPrice', 'stopLossPrice', 'confidenceLevel'
      ];

      const fieldMap = {
        reasoning: 'reasoning',
        targetPrice: 'target_price',
        stopLossPrice: 'stop_loss_price',
        confidenceLevel: 'confidence_level'
      };

      Object.keys(fieldMap).forEach(key => {
        if (req.body[key] !== undefined) {
          updates.push(`${fieldMap[key]} = $${paramIndex}`);
          values.push(req.body[key]);
          paramIndex++;
        }
      });

      if (updates.length === 0) {
        return res.status(400).json({ error: 'No fields to update' });
      }

      values.push(id);

      const result = await query(`
        UPDATE signals
        SET ${updates.join(', ')}, updated_at = CURRENT_TIMESTAMP
        WHERE id = $${paramIndex}
        RETURNING *
      `, values);

      res.json({
        message: 'Signal updated successfully',
        signal: result.rows[0]
      });

    } catch (error) {
      console.error('Update signal error:', error);
      res.status(500).json({ error: 'Failed to update signal' });
    }
  }
);

// ============================================
// CLOSE SIGNAL (Post exit)
// ============================================

router.post('/:id/close',
  requireAuth,
  requireTrader,
  param('id').isInt(),
  body('exitPrice').isInt({ min: 0 }),
  body('result').isIn(['win', 'loss', 'neutral']),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { id } = req.params;
      const { exitPrice, result: tradeResult } = req.body;
      const traderId = req.traderId;

      await transaction(async (client) => {
        // Verify ownership and get signal
        const signalResult = await client.query(
          'SELECT * FROM signals WHERE id = $1 AND trader_id = $2 AND status = $3',
          [id, traderId, 'active']
        );

        if (signalResult.rows.length === 0) {
          throw new Error('Signal not found, unauthorized, or already closed');
        }

        const signal = signalResult.rows[0];

        // Calculate ROI
        const entryPrice = signal.entry_price_max || signal.entry_price_min;
        let roi = 0;

        if (entryPrice && exitPrice) {
          roi = ((exitPrice - entryPrice) / entryPrice) * 100;
          // Account for 5% EA tax
          roi = roi - 5;
        }

        // Close signal
        await client.query(`
          UPDATE signals
          SET
            exit_price = $2,
            exit_posted_at = CURRENT_TIMESTAMP,
            status = 'closed',
            result = $3,
            roi = $4
          WHERE id = $1
        `, [id, exitPrice, tradeResult, roi]);

        // Recalculate trader stats
        await client.query('SELECT calculate_trader_win_rate($1)', [traderId]);
      });

      res.json({ message: 'Signal closed successfully' });

    } catch (error) {
      console.error('Close signal error:', error);
      res.status(500).json({ error: error.message || 'Failed to close signal' });
    }
  }
);

// ============================================
// MARK "I INVESTED"
// ============================================

router.post('/:id/invest',
  requireAuth,
  param('id').isInt(),
  async (req, res) => {
    try {
      const { id } = req.params;
      const userId = req.user.id;

      // Check if signal exists
      const signalResult = await query(
        'SELECT id FROM signals WHERE id = $1',
        [id]
      );

      if (signalResult.rows.length === 0) {
        return res.status(404).json({ error: 'Signal not found' });
      }

      // Upsert interaction
      await query(`
        INSERT INTO user_interactions (user_id, signal_id, interaction_type)
        VALUES ($1, $2, 'invested')
        ON CONFLICT (user_id, signal_id, interaction_type) DO NOTHING
      `, [userId, id]);

      // Update count on signal
      await query(`
        UPDATE signals
        SET invested_count = (
          SELECT COUNT(*) FROM user_interactions
          WHERE signal_id = $1 AND interaction_type = 'invested'
        )
        WHERE id = $1
      `, [id]);

      res.json({ message: 'Marked as invested' });

    } catch (error) {
      console.error('Invest error:', error);
      res.status(500).json({ error: 'Failed to mark as invested' });
    }
  }
);

// ============================================
// LIKE SIGNAL
// ============================================

router.post('/:id/like',
  requireAuth,
  param('id').isInt(),
  async (req, res) => {
    try {
      const { id } = req.params;
      const userId = req.user.id;

      await transaction(async (client) => {
        // Check if already liked
        const existingResult = await client.query(
          'SELECT id FROM user_interactions WHERE user_id = $1 AND signal_id = $2 AND interaction_type = $3',
          [userId, id, 'liked']
        );

        if (existingResult.rows.length > 0) {
          // Unlike
          await client.query(
            'DELETE FROM user_interactions WHERE user_id = $1 AND signal_id = $2 AND interaction_type = $3',
            [userId, id, 'liked']
          );
        } else {
          // Like
          await client.query(
            'INSERT INTO user_interactions (user_id, signal_id, interaction_type) VALUES ($1, $2, $3)',
            [userId, id, 'liked']
          );
        }

        // Update count
        await client.query(`
          UPDATE signals
          SET likes = (
            SELECT COUNT(*) FROM user_interactions
            WHERE signal_id = $1 AND interaction_type = 'liked'
          )
          WHERE id = $1
        `, [id]);
      });

      res.json({ message: 'Like toggled' });

    } catch (error) {
      console.error('Like error:', error);
      res.status(500).json({ error: 'Failed to like signal' });
    }
  }
);

// ============================================
// GET TRENDING SIGNALS
// ============================================

router.get('/trending/now',
  async (req, res) => {
    try {
      const { limit = 10 } = req.query;

      // Signals with most activity in last 24h
      const result = await query(`
        SELECT
          s.*,
          tp.display_name as trader_name,
          tp.avg_rating as trader_rating,
          u.avatar_url as trader_avatar,
          (s.invested_count + s.likes + s.views/10) as trending_score
        FROM signals s
        JOIN trader_profiles tp ON tp.id = s.trader_id
        JOIN users u ON u.id = tp.user_id
        WHERE s.created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
          AND s.is_premium = FALSE
        ORDER BY trending_score DESC
        LIMIT $1
      `, [limit]);

      res.json({ signals: result.rows });

    } catch (error) {
      console.error('Trending signals error:', error);
      res.status(500).json({ error: 'Failed to fetch trending signals' });
    }
  }
);

module.exports = router;
