const express = require('express');
const router = express.Router();

// Placeholder routes
router.get('/:id', (req, res) => {
  res.json({ message: 'Get user - TODO' });
});

router.put('/:id', (req, res) => {
  res.json({ message: 'Update user - TODO' });
});

module.exports = router;
