const express = require('express');
const jwt = require('jsonwebtoken');

const router = express.Router();
const discordApiBase = 'https://discord.com/api';
const discordTokenUrl = `${discordApiBase}/oauth2/token`;
const discordUserUrl = `${discordApiBase}/users/@me`;
const inMemoryUsers = new Map();

const buildDiscordAuthUrl = () => {
  const clientId = process.env.DISCORD_CLIENT_ID;
  const redirectUri = process.env.DISCORD_REDIRECT_URI;
  const scope = 'identify email';

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope,
  });

  return `https://discord.com/api/oauth2/authorize?${params.toString()}`;
};

const exchangeCodeForToken = async (code) => {
  const params = new URLSearchParams({
    client_id: process.env.DISCORD_CLIENT_ID,
    client_secret: process.env.DISCORD_CLIENT_SECRET,
    grant_type: 'authorization_code',
    code,
    redirect_uri: process.env.DISCORD_REDIRECT_URI,
  });

  const response = await fetch(discordTokenUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: params.toString(),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    const error = new Error('Failed to exchange code for token.');
    error.details = errorBody;
    error.status = response.status;
    throw error;
  }

  return response.json();
};

const fetchDiscordUser = async (accessToken) => {
  const response = await fetch(discordUserUrl, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    const error = new Error('Failed to fetch Discord user.');
    error.details = errorBody;
    error.status = response.status;
    throw error;
  }

  return response.json();
};

const upsertDiscordUser = async (profile, req) => {
  const { query } = require('../db');

  // Check if user exists
  const existingUser = await query(
    'SELECT * FROM users WHERE discord_id = $1',
    [profile.id]
  );

  if (existingUser.rows.length > 0) {
    // Update existing user
    const result = await query(
      `UPDATE users
       SET username = $1,
           discriminator = $2,
           avatar_url = $3,
           email = $4,
           last_login = CURRENT_TIMESTAMP,
           updated_at = CURRENT_TIMESTAMP
       WHERE discord_id = $5
       RETURNING *`,
      [
        profile.username,
        profile.discriminator,
        profile.avatar ? `https://cdn.discordapp.com/avatars/${profile.id}/${profile.avatar}.png` : null,
        profile.email,
        profile.id,
      ]
    );
    return result.rows[0];
  } else {
    // Create new user
    const result = await query(
      `INSERT INTO users (discord_id, username, discriminator, avatar_url, email)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING *`,
      [
        profile.id,
        profile.username,
        profile.discriminator,
        profile.avatar ? `https://cdn.discordapp.com/avatars/${profile.id}/${profile.avatar}.png` : null,
        profile.email,
      ]
    );
    return result.rows[0];
  }
};

const createJwt = (user) => {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    const error = new Error('JWT_SECRET is not configured.');
    error.status = 500;
    throw error;
  }

  return jwt.sign(
    {
      id: user.discordId,
      username: user.username,
      discriminator: user.discriminator,
      avatar: user.avatar,
      email: user.email,
    },
    secret,
    { expiresIn: process.env.JWT_EXPIRES_IN || '7d' },
  );
};

const extractBearerToken = (req) => {
  const header = req.headers.authorization || '';
  if (header.startsWith('Bearer ')) {
    return header.slice('Bearer '.length).trim();
  }

  return null;
};

router.get('/discord', (req, res) => {
  const discordAuthUrl = buildDiscordAuthUrl();
  res.redirect(discordAuthUrl);
});

router.get('/discord/callback', async (req, res) => {
  const { code, error } = req.query;

  if (error) {
    return res.status(400).json({ error: 'Discord authorization failed.', details: error });
  }

  if (!code) {
    return res.status(400).json({ error: 'Missing authorization code.' });
  }

  try {
    const tokenData = await exchangeCodeForToken(code);
    const discordUser = await fetchDiscordUser(tokenData.access_token);
    const storedUser = await upsertDiscordUser(discordUser, req);
    const jwtToken = createJwt(storedUser);

    // Always redirect to frontend callback with token
    const frontendUrl = process.env.FRONTEND_URL || process.env.DISCORD_SUCCESS_REDIRECT_URI || 'https://calm-radiance-production.up.railway.app';
    const callbackUrl = `${frontendUrl}/auth/callback?token=${jwtToken}`;

    // Use redirect with HTML meta refresh as fallback
    return res.type('html').send(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Redirecting...</title>
  <meta http-equiv="refresh" content="0;url=${callbackUrl}">
  <script>
    window.location.href = "${callbackUrl}";
  </script>
  <style>
    body {
      margin: 0;
      padding: 40px;
      font-family: system-ui, -apple-system, sans-serif;
      text-align: center;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-center;
    }
    .container {
      background: rgba(255,255,255,0.1);
      padding: 40px;
      border-radius: 20px;
      backdrop-filter: blur(10px);
    }
    .spinner {
      border: 4px solid rgba(255,255,255,0.3);
      border-top: 4px solid white;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: 20px auto;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    a { color: white; text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <h2>✓ Login Successful!</h2>
    <div class="spinner"></div>
    <p>Redirecting you back to FUT Hub...</p>
    <p style="opacity: 0.7; font-size: 14px;">If you are not redirected automatically, <a href="${callbackUrl}">click here</a>.</p>
  </div>
</body>
</html>`);
  } catch (err) {
    const status = err.status || 500;
    return res.status(status).json({
      error: err.message || 'Discord OAuth failed.',
      details: err.details,
    });
  }
});

// ============================================
// LOGOUT
// ============================================

router.post('/logout', (req, res) => {
  res.json({ success: true, message: 'Logged out successfully' });
});

router.get('/me', (req, res) => {
  const token = extractBearerToken(req);
  if (!token) {
    return res.status(401).json({ user: null });
  }

  try {
    const user = jwt.verify(token, process.env.JWT_SECRET);
    return res.json({ user });
  } catch (err) {
    return res.status(401).json({ user: null });
  }
});

module.exports = router;
