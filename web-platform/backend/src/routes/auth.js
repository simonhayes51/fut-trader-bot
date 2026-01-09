const express = require('express');
const router = express.Router();

// TODO: Implement Discord OAuth
// This is a placeholder for now

router.get('/discord', (req, res) => {
  // Redirect to Discord OAuth
  const discordAuthUrl = `https://discord.com/api/oauth2/authorize?client_id=${process.env.DISCORD_CLIENT_ID}&redirect_uri=${encodeURIComponent(process.env.DISCORD_REDIRECT_URI)}&response_type=code&scope=identify%20email`;
  res.redirect(discordAuthUrl);
});

router.get('/discord/callback', async (req, res) => {
  // TODO: Exchange code for token
  // TODO: Get user info from Discord
  // TODO: Create/update user in database
  // TODO: Generate JWT
  res.json({ message: 'Discord OAuth callback - TODO' });
});

router.post('/logout', (req, res) => {
  res.json({ message: 'Logged out' });
});

router.get('/me', (req, res) => {
  // TODO: Return current user from JWT
  res.json({ user: null });
});

module.exports = router;
