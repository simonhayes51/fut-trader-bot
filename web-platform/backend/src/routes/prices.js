const express = require('express');
const router = express.Router();

router.get('/check/:cardName', (req, res) => {
  res.json({
    card_name: req.params.cardName,
    ps_price: 789000,
    xbox_price: 792000,
    pc_price: 845000,
    message: 'TODO: Implement Futbin scraper'
  });
});

module.exports = router;
