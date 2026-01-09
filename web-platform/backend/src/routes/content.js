const express = require('express');
const router = express.Router();

router.get('/', (req, res) => res.json({ message: 'Browse content - TODO' }));
router.get('/:id', (req, res) => res.json({ message: 'Get content - TODO' }));
router.post('/', (req, res) => res.json({ message: 'Create content - TODO' }));

module.exports = router;
