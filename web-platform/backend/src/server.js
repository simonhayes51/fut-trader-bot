const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const compression = require('compression');
const rateLimit = require('express-rate-limit');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;

// ============================================
// MIDDLEWARE
// ============================================

// Security
app.use(helmet());

// CORS
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:3000',
  credentials: true
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use('/api/', limiter);

// Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Compression
app.use(compression());

// Logging
if (process.env.NODE_ENV !== 'production') {
  app.use(morgan('dev'));
} else {
  app.use(morgan('combined'));
}

// ============================================
// ROUTES
// ============================================

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// API Routes
app.use('/api/auth', require('./routes/auth'));
app.use('/api/users', require('./routes/users'));
app.use('/api/traders', require('./routes/traders'));
app.use('/api/signals', require('./routes/signals'));
app.use('/api/content', require('./routes/content'));
app.use('/api/subscriptions', require('./routes/subscriptions'));
app.use('/api/reviews', require('./routes/reviews'));
app.use('/api/comments', require('./routes/comments'));
app.use('/api/community', require('./routes/community'));
app.use('/api/prices', require('./routes/prices'));
app.use('/api/discord-servers', require('./routes/discordServers'));

// ============================================
// ERROR HANDLING
// ============================================

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: 'The requested resource does not exist'
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('Error:', err);

  // Don't leak error details in production
  const errorResponse = {
    error: err.name || 'Internal Server Error',
    message: process.env.NODE_ENV === 'production'
      ? 'An error occurred'
      : err.message
  };

  if (process.env.NODE_ENV !== 'production') {
    errorResponse.stack = err.stack;
  }

  res.status(err.statusCode || 500).json(errorResponse);
});

// ============================================
// START SERVER
// ============================================

app.listen(PORT, () => {
  console.log(`
  ╔═══════════════════════════════════════╗
  ║   FUT Hub API Server                  ║
  ║   Port: ${PORT}                        ║
  ║   Environment: ${process.env.NODE_ENV || 'development'}        ║
  ╚═══════════════════════════════════════╝
  `);
});

module.exports = app;
