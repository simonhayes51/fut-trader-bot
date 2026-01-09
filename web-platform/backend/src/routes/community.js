const express = require('express');
const router = express.Router();

// GET /api/community - Get community posts
router.get('/', (req, res) => {
  // For now, return empty data in the correct format
  // TODO: Implement actual community posts when database schema is ready
  res.json({
    data: {
      posts: [],
      total: 0,
      page: 1,
      limit: 20
    }
  });
});

// POST /api/community - Create community post (future feature)
router.post('/', (req, res) => {
  res.status(501).json({
    error: 'Community post creation not yet implemented',
    message: 'This feature is coming soon'
  });
});

module.exports = router;
