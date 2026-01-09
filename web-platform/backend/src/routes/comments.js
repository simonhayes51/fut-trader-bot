const express = require('express');
const router = express.Router();
const { query, transaction } = require('../db');
const { body, param, validationResult } = require('express-validator');

// ============================================
// MIDDLEWARE
// ============================================

const requireAuth = (req, res, next) => {
  // TODO: Implement real auth
  req.user = { id: 1 }; // Mock user
  next();
};

// ============================================
// GET COMMENTS (Nested/Threaded)
// ============================================

router.get('/:commentableType/:commentableId',
  param('commentableType').isIn(['signal', 'content', 'guide', 'trader']),
  param('commentableId').isInt(),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { commentableType, commentableId } = req.params;
      const { sort = 'top', limit = 50 } = req.query;

      // Sort options
      let orderBy = '(c.upvotes - c.downvotes) DESC'; // top
      if (sort === 'recent') orderBy = 'c.created_at DESC';
      if (sort === 'oldest') orderBy = 'c.created_at ASC';

      // Get all comments for this item (we'll nest them client-side or here)
      const result = await query(`
        SELECT
          c.*,
          u.username,
          u.avatar_url,
          u.is_verified_trader,
          (c.upvotes - c.downvotes) as net_votes,
          CASE
            WHEN $4::INTEGER IS NOT NULL THEN
              (SELECT vote_type FROM votes
               WHERE user_id = $4 AND votable_type = 'comment' AND votable_id = c.id)
            ELSE NULL
          END as user_vote,
          (SELECT COUNT(*) FROM comments WHERE parent_comment_id = c.id AND is_deleted = FALSE) as reply_count
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.commentable_type = $1
          AND c.commentable_id = $2
          AND c.is_deleted = FALSE
        ORDER BY
          CASE WHEN c.parent_comment_id IS NULL THEN 0 ELSE 1 END,
          ${orderBy}
        LIMIT $3
      `, [commentableType, commentableId, limit, req.user?.id || null]);

      // Organize into threaded structure
      const commentsMap = {};
      const topLevelComments = [];

      // First pass: create map of all comments
      result.rows.forEach(comment => {
        commentsMap[comment.id] = { ...comment, replies: [] };
      });

      // Second pass: nest replies
      result.rows.forEach(comment => {
        if (comment.parent_comment_id === null) {
          topLevelComments.push(commentsMap[comment.id]);
        } else {
          const parent = commentsMap[comment.parent_comment_id];
          if (parent) {
            parent.replies.push(commentsMap[comment.id]);
          }
        }
      });

      res.json({
        comments: topLevelComments,
        total: result.rows.length
      });

    } catch (error) {
      console.error('Get comments error:', error);
      res.status(500).json({ error: 'Failed to fetch comments' });
    }
  }
);

// ============================================
// POST COMMENT
// ============================================

router.post('/',
  requireAuth,
  body('commentableType').isIn(['signal', 'content', 'guide', 'trader']),
  body('commentableId').isInt(),
  body('commentText').isString().isLength({ min: 1, max: 2000 }),
  body('parentCommentId').optional().isInt(),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { commentableType, commentableId, commentText, parentCommentId } = req.body;
      const userId = req.user.id;

      // If replying to a comment, verify parent exists
      if (parentCommentId) {
        const parentResult = await query(
          'SELECT id FROM comments WHERE id = $1 AND is_deleted = FALSE',
          [parentCommentId]
        );

        if (parentResult.rows.length === 0) {
          return res.status(404).json({ error: 'Parent comment not found' });
        }
      }

      // Insert comment
      const result = await query(`
        INSERT INTO comments (user_id, commentable_type, commentable_id, comment_text, parent_comment_id)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
      `, [userId, commentableType, commentableId, commentText, parentCommentId || null]);

      // Get comment with user info
      const commentResult = await query(`
        SELECT
          c.*,
          u.username,
          u.avatar_url,
          u.is_verified_trader
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.id = $1
      `, [result.rows[0].id]);

      res.status(201).json({
        message: 'Comment posted successfully',
        comment: commentResult.rows[0]
      });

    } catch (error) {
      console.error('Post comment error:', error);
      res.status(500).json({ error: 'Failed to post comment' });
    }
  }
);

// ============================================
// UPDATE COMMENT
// ============================================

router.put('/:commentId',
  requireAuth,
  param('commentId').isInt(),
  body('commentText').isString().isLength({ min: 1, max: 2000 }),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { commentId } = req.params;
      const { commentText } = req.body;
      const userId = req.user.id;

      // Verify ownership
      const checkResult = await query(
        'SELECT id FROM comments WHERE id = $1 AND user_id = $2',
        [commentId, userId]
      );

      if (checkResult.rows.length === 0) {
        return res.status(404).json({ error: 'Comment not found or unauthorized' });
      }

      // Update comment
      const result = await query(`
        UPDATE comments
        SET
          comment_text = $2,
          is_edited = TRUE,
          updated_at = CURRENT_TIMESTAMP
        WHERE id = $1
        RETURNING *
      `, [commentId, commentText]);

      res.json({
        message: 'Comment updated successfully',
        comment: result.rows[0]
      });

    } catch (error) {
      console.error('Update comment error:', error);
      res.status(500).json({ error: 'Failed to update comment' });
    }
  }
);

// ============================================
// VOTE ON COMMENT
// ============================================

router.post('/:commentId/vote',
  requireAuth,
  param('commentId').isInt(),
  body('voteType').isIn(['upvote', 'downvote']),
  async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }

      const { commentId } = req.params;
      const { voteType } = req.body;
      const userId = req.user.id;

      await transaction(async (client) => {
        // Check if comment exists
        const commentCheck = await client.query(
          'SELECT id FROM comments WHERE id = $1 AND is_deleted = FALSE',
          [commentId]
        );

        if (commentCheck.rows.length === 0) {
          throw new Error('Comment not found');
        }

        // Remove existing vote if any
        await client.query(
          'DELETE FROM votes WHERE user_id = $1 AND votable_type = $2 AND votable_id = $3',
          [userId, 'comment', commentId]
        );

        // Insert new vote
        await client.query(
          'INSERT INTO votes (user_id, votable_type, votable_id, vote_type) VALUES ($1, $2, $3, $4)',
          [userId, 'comment', commentId, voteType]
        );

        // Update vote counts on comment
        await client.query(`
          UPDATE comments
          SET
            upvotes = (SELECT COUNT(*) FROM votes WHERE votable_type = 'comment' AND votable_id = $1 AND vote_type = 'upvote'),
            downvotes = (SELECT COUNT(*) FROM votes WHERE votable_type = 'comment' AND votable_id = $1 AND vote_type = 'downvote')
          WHERE id = $1
        `, [commentId]);
      });

      res.json({ message: 'Vote recorded successfully' });

    } catch (error) {
      console.error('Vote comment error:', error);
      res.status(500).json({ error: error.message || 'Failed to record vote' });
    }
  }
);

// ============================================
// REMOVE VOTE
// ============================================

router.delete('/:commentId/vote',
  requireAuth,
  param('commentId').isInt(),
  async (req, res) => {
    try {
      const { commentId } = req.params;
      const userId = req.user.id;

      await transaction(async (client) => {
        // Remove vote
        await client.query(
          'DELETE FROM votes WHERE user_id = $1 AND votable_type = $2 AND votable_id = $3',
          [userId, 'comment', commentId]
        );

        // Update counts
        await client.query(`
          UPDATE comments
          SET
            upvotes = (SELECT COUNT(*) FROM votes WHERE votable_type = 'comment' AND votable_id = $1 AND vote_type = 'upvote'),
            downvotes = (SELECT COUNT(*) FROM votes WHERE votable_type = 'comment' AND votable_id = $1 AND vote_type = 'downvote')
          WHERE id = $1
        `, [commentId]);
      });

      res.json({ message: 'Vote removed successfully' });

    } catch (error) {
      console.error('Remove vote error:', error);
      res.status(500).json({ error: 'Failed to remove vote' });
    }
  }
);

// ============================================
// DELETE COMMENT (Soft delete)
// ============================================

router.delete('/:commentId',
  requireAuth,
  param('commentId').isInt(),
  async (req, res) => {
    try {
      const { commentId } = req.params;
      const userId = req.user.id;

      // Verify ownership
      const checkResult = await query(
        'SELECT id FROM comments WHERE id = $1 AND user_id = $2',
        [commentId, userId]
      );

      if (checkResult.rows.length === 0) {
        return res.status(404).json({ error: 'Comment not found or unauthorized' });
      }

      // Soft delete (keep structure for nested replies)
      await query(`
        UPDATE comments
        SET
          is_deleted = TRUE,
          comment_text = '[deleted]',
          updated_at = CURRENT_TIMESTAMP
        WHERE id = $1
      `, [commentId]);

      res.json({ message: 'Comment deleted successfully' });

    } catch (error) {
      console.error('Delete comment error:', error);
      res.status(500).json({ error: 'Failed to delete comment' });
    }
  }
);

// ============================================
// PIN COMMENT (Traders only)
// ============================================

router.post('/:commentId/pin',
  requireAuth,
  param('commentId').isInt(),
  async (req, res) => {
    try {
      const { commentId } = req.params;
      const userId = req.user.id;

      // Check if user is trader and comment is on their content
      const result = await query(`
        SELECT c.*, tp.user_id as trader_user_id
        FROM comments c
        LEFT JOIN signals s ON c.commentable_type = 'signal' AND c.commentable_id = s.id
        LEFT JOIN trader_profiles tp ON s.trader_id = tp.id
        WHERE c.id = $1
      `, [commentId]);

      if (result.rows.length === 0) {
        return res.status(404).json({ error: 'Comment not found' });
      }

      const comment = result.rows[0];

      // Verify user is the trader who owns this content
      if (comment.trader_user_id !== userId) {
        return res.status(403).json({ error: 'Only the content owner can pin comments' });
      }

      // Unpin all other comments on this item, then pin this one
      await transaction(async (client) => {
        await client.query(`
          UPDATE comments
          SET is_pinned = FALSE
          WHERE commentable_type = $1 AND commentable_id = $2
        `, [comment.commentable_type, comment.commentable_id]);

        await client.query(
          'UPDATE comments SET is_pinned = TRUE WHERE id = $1',
          [commentId]
        );
      });

      res.json({ message: 'Comment pinned successfully' });

    } catch (error) {
      console.error('Pin comment error:', error);
      res.status(500).json({ error: 'Failed to pin comment' });
    }
  }
);

module.exports = router;
