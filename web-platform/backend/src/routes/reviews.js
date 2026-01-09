const express = require('express');
const router = express.Router();
const { query, transaction } = require('../db');
const { body, param, validationResult } = require('express-validator');

// ============================================
// MIDDLEWARE
// ============================================

// Mock auth middleware (replace with real auth)
const requireAuth = (req, res, next) => {
  // TODO: Implement real auth checking JWT token
  req.user = { id: 1 }; // Mock user
  next();
};

// ============================================
// GET REVIEWS
// ============================================

// Get reviews for a specific item (trader, content, signal)
router.get('/:reviewableType/:reviewableId',
  param('reviewableType').isIn(['trader', 'content', 'signal']),
  param('reviewableId').isInt(),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { reviewableType, reviewableId } = req.params;
      const { sort = 'helpful', limit = 20, offset = 0 } = req.query;

      // Sort options
      let orderBy = 'r.helpful_count DESC';
      if (sort === 'recent') orderBy = 'r.created_at DESC';
      if (sort === 'rating_high') orderBy = 'r.rating DESC';
      if (sort === 'rating_low') orderBy = 'r.rating ASC';

      const result = await query(`
        SELECT
          r.*,
          u.username,
          u.avatar_url,
          u.is_verified_trader,
          (r.helpful_count - r.unhelpful_count) as net_helpful,
          CASE
            WHEN $4::INTEGER IS NOT NULL THEN
              (SELECT vote_type FROM votes
               WHERE user_id = $4 AND votable_type = 'review' AND votable_id = r.id)
            ELSE NULL
          END as user_vote
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.reviewable_type = $1 AND r.reviewable_id = $2
        ORDER BY ${orderBy}
        LIMIT $3 OFFSET $5
      `, [reviewableType, reviewableId, limit, req.user?.id || null, offset]);

      // Get summary stats
      const statsResult = await query(`
        SELECT
          COUNT(*) as total_reviews,
          AVG(rating)::DECIMAL(3,2) as avg_rating,
          COUNT(CASE WHEN rating = 5 THEN 1 END) as five_star,
          COUNT(CASE WHEN rating = 4 THEN 1 END) as four_star,
          COUNT(CASE WHEN rating = 3 THEN 1 END) as three_star,
          COUNT(CASE WHEN rating = 2 THEN 1 END) as two_star,
          COUNT(CASE WHEN rating = 1 THEN 1 END) as one_star
        FROM reviews
        WHERE reviewable_type = $1 AND reviewable_id = $2
      `, [reviewableType, reviewableId]);

      res.json({
        reviews: result.rows,
        stats: statsResult.rows[0],
        pagination: {
          limit: parseInt(limit),
          offset: parseInt(offset),
          total: parseInt(statsResult.rows[0].total_reviews)
        }
      });

    } catch (error) {
      console.error('Get reviews error:', error);
      res.status(500).json({ error: 'Failed to fetch reviews' });
    }
  }
);

// ============================================
// CREATE REVIEW
// ============================================

router.post('/',
  requireAuth,
  body('reviewableType').isIn(['trader', 'content', 'signal']),
  body('reviewableId').isInt(),
  body('rating').isInt({ min: 1, max: 5 }),
  body('title').optional().isString().isLength({ max: 255 }),
  body('reviewText').optional().isString().isLength({ max: 2000 }),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { reviewableType, reviewableId, rating, title, reviewText } = req.body;
      const userId = req.user.id;

      // Use transaction to insert review and update averages
      const result = await transaction(async (client) => {
        // Check if user already reviewed this
        const existingReview = await client.query(
          'SELECT id FROM reviews WHERE user_id = $1 AND reviewable_type = $2 AND reviewable_id = $3',
          [userId, reviewableType, reviewableId]
        );

        if (existingReview.rows.length > 0) {
          throw new Error('You have already reviewed this item');
        }

        // Insert review
        const reviewResult = await client.query(`
          INSERT INTO reviews (user_id, reviewable_type, reviewable_id, rating, title, review_text)
          VALUES ($1, $2, $3, $4, $5, $6)
          RETURNING *
        `, [userId, reviewableType, reviewableId, rating, title, reviewText]);

        // Update average rating on the reviewed item
        if (reviewableType === 'trader') {
          await client.query(`
            UPDATE trader_profiles
            SET
              avg_rating = (SELECT AVG(rating)::DECIMAL(3,2) FROM reviews WHERE reviewable_type = 'trader' AND reviewable_id = $1),
              total_reviews = (SELECT COUNT(*) FROM reviews WHERE reviewable_type = 'trader' AND reviewable_id = $1)
            WHERE id = $1
          `, [reviewableId]);
        } else if (reviewableType === 'content') {
          await client.query(`
            UPDATE content
            SET
              avg_rating = (SELECT AVG(rating)::DECIMAL(3,2) FROM reviews WHERE reviewable_type = 'content' AND reviewable_id = $1),
              total_reviews = (SELECT COUNT(*) FROM reviews WHERE reviewable_type = 'content' AND reviewable_id = $1)
            WHERE id = $1
          `, [reviewableId]);
        }

        return reviewResult.rows[0];
      });

      res.status(201).json({
        message: 'Review created successfully',
        review: result
      });

    } catch (error) {
      console.error('Create review error:', error);
      res.status(error.message === 'You have already reviewed this item' ? 400 : 500)
        .json({ error: error.message || 'Failed to create review' });
    }
  }
);

// ============================================
// UPDATE REVIEW
// ============================================

router.put('/:reviewId',
  requireAuth,
  param('reviewId').isInt(),
  body('rating').optional().isInt({ min: 1, max: 5 }),
  body('title').optional().isString().isLength({ max: 255 }),
  body('reviewText').optional().isString().isLength({ max: 2000 }),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { reviewId } = req.params;
      const { rating, title, reviewText } = req.body;
      const userId = req.user.id;

      const result = await transaction(async (client) => {
        // Check ownership
        const checkResult = await client.query(
          'SELECT reviewable_type, reviewable_id FROM reviews WHERE id = $1 AND user_id = $2',
          [reviewId, userId]
        );

        if (checkResult.rows.length === 0) {
          throw new Error('Review not found or unauthorized');
        }

        const { reviewable_type, reviewable_id } = checkResult.rows[0];

        // Update review
        const updateResult = await client.query(`
          UPDATE reviews
          SET
            rating = COALESCE($2, rating),
            title = COALESCE($3, title),
            review_text = COALESCE($4, review_text),
            updated_at = CURRENT_TIMESTAMP
          WHERE id = $1
          RETURNING *
        `, [reviewId, rating, title, reviewText]);

        // Recalculate averages
        if (reviewable_type === 'trader') {
          await client.query(`
            UPDATE trader_profiles
            SET avg_rating = (SELECT AVG(rating)::DECIMAL(3,2) FROM reviews WHERE reviewable_type = 'trader' AND reviewable_id = $1)
            WHERE id = $1
          `, [reviewable_id]);
        } else if (reviewable_type === 'content') {
          await client.query(`
            UPDATE content
            SET avg_rating = (SELECT AVG(rating)::DECIMAL(3,2) FROM reviews WHERE reviewable_type = 'content' AND reviewable_id = $1)
            WHERE id = $1
          `, [reviewable_id]);
        }

        return updateResult.rows[0];
      });

      res.json({
        message: 'Review updated successfully',
        review: result
      });

    } catch (error) {
      console.error('Update review error:', error);
      res.status(500).json({ error: error.message || 'Failed to update review' });
    }
  }
);

// ============================================
// VOTE ON REVIEW (Helpful/Unhelpful)
// ============================================

router.post('/:reviewId/vote',
  requireAuth,
  param('reviewId').isInt(),
  body('voteType').isIn(['helpful', 'unhelpful']),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { reviewId } = req.params;
      const { voteType } = req.body;
      const userId = req.user.id;

      await transaction(async (client) => {
        // Remove existing vote if any
        await client.query(
          'DELETE FROM votes WHERE user_id = $1 AND votable_type = $2 AND votable_id = $3',
          [userId, 'review', reviewId]
        );

        // Insert new vote
        await client.query(
          'INSERT INTO votes (user_id, votable_type, votable_id, vote_type) VALUES ($1, $2, $3, $4)',
          [userId, 'review', reviewId, voteType]
        );

        // Update counts on review
        await client.query(`
          UPDATE reviews
          SET
            helpful_count = (SELECT COUNT(*) FROM votes WHERE votable_type = 'review' AND votable_id = $1 AND vote_type = 'helpful'),
            unhelpful_count = (SELECT COUNT(*) FROM votes WHERE votable_type = 'review' AND votable_id = $1 AND vote_type = 'unhelpful')
          WHERE id = $1
        `, [reviewId]);
      });

      res.json({ message: 'Vote recorded successfully' });

    } catch (error) {
      console.error('Vote review error:', error);
      res.status(500).json({ error: 'Failed to record vote' });
    }
  }
);

// ============================================
// DELETE REVIEW
// ============================================

router.delete('/:reviewId',
  requireAuth,
  param('reviewId').isInt(),
  async (req, res) => {
    try {
      const { reviewId } = req.params;
      const userId = req.user.id;

      await transaction(async (client) => {
        // Get review info before deleting
        const reviewResult = await client.query(
          'SELECT reviewable_type, reviewable_id FROM reviews WHERE id = $1 AND user_id = $2',
          [reviewId, userId]
        );

        if (reviewResult.rows.length === 0) {
          throw new Error('Review not found or unauthorized');
        }

        const { reviewable_type, reviewable_id } = reviewResult.rows[0];

        // Delete review
        await client.query('DELETE FROM reviews WHERE id = $1', [reviewId]);

        // Recalculate averages
        if (reviewable_type === 'trader') {
          await client.query(`
            UPDATE trader_profiles
            SET
              avg_rating = COALESCE((SELECT AVG(rating)::DECIMAL(3,2) FROM reviews WHERE reviewable_type = 'trader' AND reviewable_id = $1), 0),
              total_reviews = (SELECT COUNT(*) FROM reviews WHERE reviewable_type = 'trader' AND reviewable_id = $1)
            WHERE id = $1
          `, [reviewable_id]);
        } else if (reviewable_type === 'content') {
          await client.query(`
            UPDATE content
            SET
              avg_rating = COALESCE((SELECT AVG(rating)::DECIMAL(3,2) FROM reviews WHERE reviewable_type = 'content' AND reviewable_id = $1), 0),
              total_reviews = (SELECT COUNT(*) FROM reviews WHERE reviewable_type = 'content' AND reviewable_id = $1)
            WHERE id = $1
          `, [reviewable_id]);
        }
      });

      res.json({ message: 'Review deleted successfully' });

    } catch (error) {
      console.error('Delete review error:', error);
      res.status(500).json({ error: error.message || 'Failed to delete review' });
    }
  }
);

module.exports = router;
