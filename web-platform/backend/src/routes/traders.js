const express = require('express');
const router = express.Router();
const { query, transaction } = require('../db');
const { body, param, validationResult } = require('express-validator');

// ============================================
// MIDDLEWARE
// ============================================

const requireAuth = (req, res, next) => {
  // TODO: Implement real auth
  req.user = { id: 1 };
  next();
};

// ============================================
// BROWSE TRADERS
// ============================================

router.get('/',
  async (req, res) => {
    try {
      const {
        sort = 'win_rate',
        specialty,
        min_rating,
        max_price,
        limit = 20,
        offset = 0
      } = req.query;

      // Build WHERE clause
      let whereConditions = ['tp.is_accepting_subscribers = TRUE'];
      const queryParams = [];
      let paramIndex = 1;

      if (specialty) {
        queryParams.push(specialty);
        whereConditions.push(`$${paramIndex} = ANY(tp.specialties)`);
        paramIndex++;
      }

      if (min_rating) {
        queryParams.push(parseFloat(min_rating));
        whereConditions.push(`tp.avg_rating >= $${paramIndex}`);
        paramIndex++;
      }

      if (max_price) {
        queryParams.push(parseFloat(max_price));
        whereConditions.push(`tp.subscription_price_monthly <= $${paramIndex}`);
        paramIndex++;
      }

      // Build ORDER BY clause
      let orderBy = 'tp.win_rate DESC, tp.avg_rating DESC';
      if (sort === 'rating') orderBy = 'tp.avg_rating DESC, tp.total_reviews DESC';
      if (sort === 'subscribers') orderBy = 'tp.total_subscribers DESC';
      if (sort === 'price_low') orderBy = 'tp.subscription_price_monthly ASC';
      if (sort === 'price_high') orderBy = 'tp.subscription_price_monthly DESC';

      queryParams.push(limit, offset);

      const result = await query(`
        SELECT
          tp.*,
          u.username,
          u.avatar_url,
          u.is_verified_trader,
          tp.subscription_price_monthly as subscription_price,
          tp.total_reviews as review_count,
          (SELECT COUNT(*) FROM signals WHERE trader_id = tp.id AND status = 'active') as active_signals_count
        FROM trader_profiles tp
        JOIN users u ON u.id = tp.user_id
        WHERE ${whereConditions.join(' AND ')}
        ORDER BY ${orderBy}
        LIMIT $${paramIndex} OFFSET $${paramIndex + 1}
      `, queryParams);

      // Get total count
      const countResult = await query(`
        SELECT COUNT(*) as total
        FROM trader_profiles tp
        WHERE ${whereConditions.join(' AND ')}
      `, queryParams.slice(0, -2));

      res.json({
        traders: result.rows,
        pagination: {
          total: parseInt(countResult.rows[0].total),
          limit: parseInt(limit),
          offset: parseInt(offset)
        }
      });

    } catch (error) {
      console.error('Browse traders error:', error);
      res.status(500).json({ error: 'Failed to fetch traders' });
    }
  }
);

// ============================================
// GET TRADER PROFILE
// ============================================

router.get('/:id',
  param('id').isInt(),
  async (req, res) => {
    try {
      const { id } = req.params;
      const userId = req.user?.id;

      // Get trader profile
      const traderResult = await query(`
        SELECT
          tp.*,
          u.username,
          u.avatar_url,
          u.is_verified_trader,
          u.created_at as user_joined,
          CASE
            WHEN $2::INTEGER IS NOT NULL THEN
              (SELECT TRUE FROM subscriptions
               WHERE user_id = $2 AND trader_id = tp.id AND status = 'active')
            ELSE FALSE
          END as is_subscribed
        FROM trader_profiles tp
        JOIN users u ON u.id = tp.user_id
        WHERE tp.id = $1
      `, [id, userId]);

      if (traderResult.rows.length === 0) {
        return res.status(404).json({ error: 'Trader not found' });
      }

      const trader = traderResult.rows[0];

      // Get recent signals (free + premium if subscribed)
      const signalsResult = await query(`
        SELECT
          s.*,
          (SELECT COUNT(*) FROM user_interactions WHERE signal_id = s.id AND interaction_type = 'invested') as invested_count
        FROM signals s
        WHERE s.trader_id = $1
          AND (s.is_premium = FALSE OR $2 = TRUE)
        ORDER BY s.created_at DESC
        LIMIT 10
      `, [id, trader.is_subscribed]);

      // Get signal stats
      const statsResult = await query(`
        SELECT
          COUNT(*) FILTER (WHERE status = 'closed' AND result = 'win') as wins,
          COUNT(*) FILTER (WHERE status = 'closed' AND result = 'loss') as losses,
          AVG(roi) FILTER (WHERE status = 'closed' AND result = 'win') as avg_win_roi,
          MAX(roi) FILTER (WHERE status = 'closed') as best_roi,
          COUNT(*) FILTER (WHERE status = 'active') as active_count
        FROM signals
        WHERE trader_id = $1
      `, [id]);

      res.json({
        trader,
        recent_signals: signalsResult.rows,
        stats: statsResult.rows[0]
      });

    } catch (error) {
      console.error('Get trader error:', error);
      res.status(500).json({ error: 'Failed to fetch trader' });
    }
  }
);

// ============================================
// CREATE TRADER PROFILE
// ============================================

router.post('/',
  requireAuth,
  body('displayName').isString().isLength({ min: 3, max: 255 }),
  body('bio').optional().isString().isLength({ max: 1000 }),
  body('specialties').isArray(),
  body('subscriptionPrice').isFloat({ min: 2.99, max: 49.99 }),
  body('subscriptionPriceVip').optional().isFloat({ min: 2.99, max: 99.99 }),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { displayName, bio, specialties, subscriptionPrice, subscriptionPriceVip } = req.body;
      const userId = req.user.id;

      const result = await transaction(async (client) => {
        // Check if user already has trader profile
        const existingResult = await client.query(
          'SELECT id FROM trader_profiles WHERE user_id = $1',
          [userId]
        );

        if (existingResult.rows.length > 0) {
          throw new Error('You already have a trader profile');
        }

        // Create trader profile
        const profileResult = await client.query(`
          INSERT INTO trader_profiles (
            user_id, display_name, bio, specialties,
            subscription_price_monthly, subscription_price_vip
          )
          VALUES ($1, $2, $3, $4, $5, $6)
          RETURNING *
        `, [userId, displayName, bio, specialties, subscriptionPrice, subscriptionPriceVip || null]);

        // Update user to be trader
        await client.query(
          'UPDATE users SET is_trader = TRUE WHERE id = $1',
          [userId]
        );

        return profileResult.rows[0];
      });

      res.status(201).json({
        message: 'Trader profile created successfully',
        trader: result
      });

    } catch (error) {
      console.error('Create trader error:', error);
      res.status(error.message === 'You already have a trader profile' ? 400 : 500)
        .json({ error: error.message || 'Failed to create trader profile' });
    }
  }
);

// ============================================
// UPDATE TRADER PROFILE
// ============================================

router.put('/:id',
  requireAuth,
  param('id').isInt(),
  body('displayName').optional().isString().isLength({ min: 3, max: 255 }),
  body('bio').optional().isString().isLength({ max: 1000 }),
  body('specialties').optional().isArray(),
  body('subscriptionPrice').optional().isFloat({ min: 2.99, max: 49.99 }),
  body('subscriptionPriceVip').optional().isFloat({ min: 2.99, max: 99.99 }),
  body('twitterHandle').optional().isString(),
  body('twitchHandle').optional().isString(),
  body('youtubeUrl').optional().isURL(),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { id } = req.params;
      const userId = req.user.id;

      // Verify ownership
      const checkResult = await query(
        'SELECT id FROM trader_profiles WHERE id = $1 AND user_id = $2',
        [id, userId]
      );

      if (checkResult.rows.length === 0) {
        return res.status(404).json({ error: 'Trader profile not found or unauthorized' });
      }

      // Build UPDATE query dynamically
      const updates = [];
      const values = [];
      let paramIndex = 1;

      const fieldMap = {
        displayName: 'display_name',
        bio: 'bio',
        specialties: 'specialties',
        subscriptionPrice: 'subscription_price_monthly',
        subscriptionPriceVip: 'subscription_price_vip',
        twitterHandle: 'twitter_handle',
        twitchHandle: 'twitch_handle',
        youtubeUrl: 'youtube_url'
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
        UPDATE trader_profiles
        SET ${updates.join(', ')}, updated_at = CURRENT_TIMESTAMP
        WHERE id = $${paramIndex}
        RETURNING *
      `, values);

      res.json({
        message: 'Trader profile updated successfully',
        trader: result.rows[0]
      });

    } catch (error) {
      console.error('Update trader error:', error);
      res.status(500).json({ error: 'Failed to update trader profile' });
    }
  }
);

// ============================================
// GET TRADER'S SIGNALS
// ============================================

router.get('/:id/signals',
  param('id').isInt(),
  async (req, res) => {
    try {
      const { id } = req.params;
      const { status = 'all', limit = 20, offset = 0 } = req.query;
      const userId = req.user?.id;

      // Check if user is subscribed
      let isSubscribed = false;
      if (userId) {
        const subResult = await query(
          'SELECT id FROM subscriptions WHERE user_id = $1 AND trader_id = $2 AND status = $3',
          [userId, id, 'active']
        );
        isSubscribed = subResult.rows.length > 0;
      }

      // Build WHERE clause
      let whereConditions = ['s.trader_id = $1'];
      const queryParams = [id];
      let paramIndex = 2;

      // Only show free signals if not subscribed
      if (!isSubscribed) {
        whereConditions.push('s.is_premium = FALSE');
      }

      if (status !== 'all') {
        queryParams.push(status);
        whereConditions.push(`s.status = $${paramIndex}`);
        paramIndex++;
      }

      queryParams.push(limit, offset);

      const result = await query(`
        SELECT
          s.*,
          (SELECT COUNT(*) FROM user_interactions WHERE signal_id = s.id AND interaction_type = 'invested') as invested_count,
          (SELECT COUNT(*) FROM comments WHERE commentable_type = 'signal' AND commentable_id = s.id) as comment_count
        FROM signals s
        WHERE ${whereConditions.join(' AND ')}
        ORDER BY s.created_at DESC
        LIMIT $${paramIndex} OFFSET $${paramIndex + 1}
      `, queryParams);

      res.json({
        signals: result.rows,
        is_subscribed: isSubscribed
      });

    } catch (error) {
      console.error('Get trader signals error:', error);
      res.status(500).json({ error: 'Failed to fetch signals' });
    }
  }
);

// ============================================
// GET TRADER STATS
// ============================================

router.get('/:id/stats',
  param('id').isInt(),
  async (req, res) => {
    try {
      const { id } = req.params;
      const { timeframe = '30d' } = req.query;

      // Calculate date filter
      let dateFilter = "created_at >= CURRENT_DATE - INTERVAL '30 days'";
      if (timeframe === '7d') dateFilter = "created_at >= CURRENT_DATE - INTERVAL '7 days'";
      if (timeframe === '90d') dateFilter = "created_at >= CURRENT_DATE - INTERVAL '90 days'";
      if (timeframe === 'all') dateFilter = 'TRUE';

      // Get detailed stats
      const result = await query(`
        SELECT
          COUNT(*) FILTER (WHERE status = 'closed') as total_closed,
          COUNT(*) FILTER (WHERE status = 'closed' AND result = 'win') as total_wins,
          COUNT(*) FILTER (WHERE status = 'closed' AND result = 'loss') as total_losses,
          COUNT(*) FILTER (WHERE status = 'active') as total_active,

          AVG(roi) FILTER (WHERE status = 'closed') as avg_roi,
          AVG(roi) FILTER (WHERE status = 'closed' AND result = 'win') as avg_win_roi,
          AVG(roi) FILTER (WHERE status = 'closed' AND result = 'loss') as avg_loss_roi,

          MAX(roi) FILTER (WHERE status = 'closed') as best_trade,
          MIN(roi) FILTER (WHERE status = 'closed') as worst_trade,

          AVG(EXTRACT(EPOCH FROM (exit_posted_at - entry_posted_at))/86400)
            FILTER (WHERE status = 'closed') as avg_hold_days,

          COUNT(*) FILTER (WHERE risk_level = 'Low') as low_risk_count,
          COUNT(*) FILTER (WHERE risk_level = 'Medium') as medium_risk_count,
          COUNT(*) FILTER (WHERE risk_level = 'High') as high_risk_count
        FROM signals
        WHERE trader_id = $1 AND ${dateFilter}
      `, [id]);

      // Get performance by card type
      const cardTypeResult = await query(`
        SELECT
          card_position,
          COUNT(*) as total,
          COUNT(*) FILTER (WHERE result = 'win') as wins,
          AVG(roi) as avg_roi
        FROM signals
        WHERE trader_id = $1 AND status = 'closed' AND ${dateFilter}
        GROUP BY card_position
        ORDER BY total DESC
        LIMIT 10
      `, [id]);

      // Get monthly performance trend
      const trendResult = await query(`
        SELECT
          DATE_TRUNC('month', entry_posted_at) as month,
          COUNT(*) FILTER (WHERE result = 'win') as wins,
          COUNT(*) FILTER (WHERE result = 'loss') as losses,
          AVG(roi) as avg_roi
        FROM signals
        WHERE trader_id = $1 AND status = 'closed' AND ${dateFilter}
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
      `, [id]);

      res.json({
        overall: result.rows[0],
        by_card_type: cardTypeResult.rows,
        monthly_trend: trendResult.rows
      });

    } catch (error) {
      console.error('Get trader stats error:', error);
      res.status(500).json({ error: 'Failed to fetch stats' });
    }
  }
);

// ============================================
// TOP TRADERS (Leaderboard)
// ============================================

router.get('/leaderboard/top',
  async (req, res) => {
    try {
      const { metric = 'win_rate', limit = 10 } = req.query;

      let orderBy = 'tp.win_rate DESC';
      if (metric === 'rating') orderBy = 'tp.avg_rating DESC, tp.total_reviews DESC';
      if (metric === 'subscribers') orderBy = 'tp.total_subscribers DESC';
      if (metric === 'signals') orderBy = 'tp.total_signals DESC';

      const result = await query(`
        SELECT
          tp.id,
          tp.display_name,
          tp.specialties,
          tp.win_rate,
          tp.avg_rating,
          tp.total_reviews,
          tp.total_subscribers,
          tp.total_signals,
          u.username,
          u.avatar_url,
          u.is_verified_trader
        FROM trader_profiles tp
        JOIN users u ON u.id = tp.user_id
        WHERE tp.total_signals >= 10  -- Must have at least 10 signals
        ORDER BY ${orderBy}
        LIMIT $1
      `, [limit]);

      res.json({ traders: result.rows });

    } catch (error) {
      console.error('Get leaderboard error:', error);
      res.status(500).json({ error: 'Failed to fetch leaderboard' });
    }
  }
);

module.exports = router;
