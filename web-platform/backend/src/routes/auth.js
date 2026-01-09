const express = require('express');
const router = express.Router();
const axios = require('axios');
const jwt = require('jsonwebtoken');
const { query } = require('../db');

// ============================================
// DISCORD OAUTH - LOGIN/SIGNUP
// ============================================

router.get('/discord', (req, res) => {
  const discordAuthUrl = `https://discord.com/api/oauth2/authorize?client_id=${process.env.DISCORD_CLIENT_ID}&redirect_uri=${encodeURIComponent(process.env.DISCORD_REDIRECT_URI)}&response_type=code&scope=identify%20email`;
  res.redirect(discordAuthUrl);
});

router.get('/discord/callback', async (req, res) => {
  const { code } = req.query;

  if (!code) {
    return res.redirect(`${process.env.FRONTEND_URL}/login?error=no_code`);
  }

  try {
    // Exchange code for access token
    const tokenResponse = await axios.post(
      'https://discord.com/api/oauth2/token',
      new URLSearchParams({
        client_id: process.env.DISCORD_CLIENT_ID,
        client_secret: process.env.DISCORD_CLIENT_SECRET,
        grant_type: 'authorization_code',
        code: code,
        redirect_uri: process.env.DISCORD_REDIRECT_URI,
      }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    const { access_token } = tokenResponse.data;

    // Get user info from Discord
    const userResponse = await axios.get('https://discord.com/api/users/@me', {
      headers: {
        Authorization: `Bearer ${access_token}`,
      },
    });

    const discordUser = userResponse.data;

    // Create or update user in database
    const existingUser = await query(
      'SELECT * FROM users WHERE discord_id = $1',
      [discordUser.id]
    );

    let userId;

    if (existingUser.rows.length > 0) {
      // Update existing user
      await query(
        `UPDATE users
         SET username = $1,
             discriminator = $2,
             avatar_url = $3,
             email = $4,
             last_login = CURRENT_TIMESTAMP
         WHERE discord_id = $5`,
        [
          discordUser.username,
          discordUser.discriminator,
          discordUser.avatar
            ? `https://cdn.discordapp.com/avatars/${discordUser.id}/${discordUser.avatar}.png`
            : null,
          discordUser.email,
          discordUser.id,
        ]
      );
      userId = existingUser.rows[0].id;
    } else {
      // Create new user
      const newUser = await query(
        `INSERT INTO users (discord_id, username, discriminator, avatar_url, email)
         VALUES ($1, $2, $3, $4, $5)
         RETURNING id`,
        [
          discordUser.id,
          discordUser.username,
          discordUser.discriminator,
          discordUser.avatar
            ? `https://cdn.discordapp.com/avatars/${discordUser.id}/${discordUser.avatar}.png`
            : null,
          discordUser.email,
        ]
      );
      userId = newUser.rows[0].id;
    }

    // Generate JWT token
    const token = jwt.sign(
      {
        userId: userId,
        discordId: discordUser.id,
        username: discordUser.username
      },
      process.env.JWT_SECRET,
      { expiresIn: '30d' }
    );

    // Redirect to frontend with token
    res.redirect(`${process.env.FRONTEND_URL}/auth/callback?token=${token}`);

  } catch (error) {
    console.error('Discord OAuth error:', error.response?.data || error.message);
    res.redirect(`${process.env.FRONTEND_URL}/login?error=auth_failed`);
  }
});

// ============================================
// LOGOUT
// ============================================

router.post('/logout', (req, res) => {
  res.json({ success: true, message: 'Logged out successfully' });
});

// ============================================
// GET CURRENT USER
// ============================================

router.get('/me', async (req, res) => {
  try {
    const token = req.headers.authorization?.replace('Bearer ', '');

    if (!token) {
      return res.status(401).json({ error: 'Not authenticated' });
    }

    const decoded = jwt.verify(token, process.env.JWT_SECRET);

    const user = await query(
      `SELECT u.*,
              (SELECT id FROM trader_profiles WHERE user_id = u.id) as trader_profile_id
       FROM users u
       WHERE u.id = $1`,
      [decoded.userId]
    );

    if (user.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json({ user: user.rows[0] });

  } catch (error) {
    console.error('Get user error:', error);
    res.status(401).json({ error: 'Invalid token' });
  }
});

module.exports = router;
