const express = require('express');
const router = express.Router();

router.get('/', (req, res) => res.json({ servers: [] }));
router.post('/', (req, res) => res.json({ message: 'Submit server - TODO' }));

module.exports = router;
