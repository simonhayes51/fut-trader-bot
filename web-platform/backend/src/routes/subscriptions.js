const express = require('express');
const router = express.Router();

router.get('/mine', (req, res) => res.json({ subscriptions: [] }));
router.post('/', (req, res) => res.json({ message: 'Subscribe - TODO (Stripe integration)' }));
router.delete('/:id', (req, res) => res.json({ message: 'Cancel subscription - TODO' }));

module.exports = router;
