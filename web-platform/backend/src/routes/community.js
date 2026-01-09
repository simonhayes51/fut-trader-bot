const express = require('express');
const router = express.Router();

router.get('/', (req, res) => res.json({ content: [] }));
router.post('/', (req, res) => res.json({ message: 'Create community content - TODO' }));

module.exports = router;
