# FUT Hub - Trading Platform

A comprehensive platform connecting FUT traders with the community. Think OnlyFans meets Patreon for FIFA Ultimate Team trading.

## 🎯 Core Features

### For Traders (Content Creators)
- **Subscription-based income** - Set your own monthly price (£2.99-49.99)
- **One-off content sales** - Sell guides, courses, templates
- **Performance tracking** - Auto-calculated win rates, ROI stats
- **Community ratings** - Build reputation through reviews
- **Keep 75%** of all earnings

### For Users (Traders/Investors)
- **Subscribe to proven traders** - Follow traders with verified track records
- **Interactive community** - Comments, reviews, discussions
- **Free tools** - Price checker, portfolio tracker, SBC solutions
- **Price alerts** - Get notified when cards hit your targets
- **Discord integration** - Seamless login and notifications

### Platform Features
- ✅ **Reviews & Ratings** - 5-star system with detailed feedback
- ✅ **Nested Comments** - Threaded discussions with voting
- ✅ **Content Voting** - Upvote/downvote system like Reddit
- ✅ **Real-time prices** - Scraped from Futbin every 5-10 minutes
- ✅ **Discord directory** - Discover trading servers
- ✅ **Community content** - User-generated guides and tips

---

## 📊 Database Schema

### Core Tables

**Users & Authentication:**
- `users` - Discord OAuth user accounts
- `trader_profiles` - Trader-specific data and stats

**Trading Signals:**
- `signals` - Buy/sell signals from traders
- `user_interactions` - Track who invested in what

**Monetization:**
- `subscriptions` - Monthly subscriptions (Stripe)
- `content` - One-off products (guides, courses)
- `purchases` - One-time content purchases

**Community & Engagement:**
- `reviews` - Star ratings with text (polymorphic)
- `comments` - Nested/threaded comments (polymorphic)
- `votes` - Upvote/downvote system (polymorphic)
- `community_content` - User-generated guides/tips

**Utilities:**
- `price_data` - Scraped market prices
- `discord_servers` - Server directory
- `notifications` - User notifications

### Polymorphic Relationships

The platform uses polymorphic associations for maximum flexibility:

**Reviews can be on:**
- Traders (rate a trader's performance)
- Content (rate a guide/course)
- Signals (rate a specific trade call)

**Comments can be on:**
- Signals (discuss a trade)
- Content (ask questions about guides)
- Traders (general discussion)
- Community guides

**Votes can be on:**
- Comments (upvote/downvote)
- Reviews (helpful/unhelpful)
- Community content

---

## 🏗️ Architecture

### Backend (Node.js/Express)

```
backend/
├── src/
│   ├── server.js              # Main Express app
│   ├── db/
│   │   └── index.js           # PostgreSQL connection pool
│   ├── routes/
│   │   ├── auth.js            # Discord OAuth
│   │   ├── traders.js         # Trader profiles & stats
│   │   ├── signals.js         # Trading signals
│   │   ├── content.js         # One-off products
│   │   ├── subscriptions.js   # Stripe subscriptions
│   │   ├── reviews.js         # ⭐ Rating system
│   │   ├── comments.js        # 💬 Nested comments
│   │   ├── community.js       # User guides
│   │   ├── prices.js          # Price scraper
│   │   └── discordServers.js  # Server directory
│   ├── middleware/
│   │   ├── auth.js            # JWT verification
│   │   └── validation.js      # Input validation
│   └── services/
│       ├── stripe.js          # Payment processing
│       ├── scraper.js         # Futbin price scraper
│       └── discord.js         # Discord webhooks/DMs
└── package.json
```

### Frontend (Next.js/React)

```
frontend/
├── pages/
│   ├── index.js               # Homepage
│   ├── traders/
│   │   ├── [id].js            # Trader profile
│   │   └── discover.js        # Browse traders
│   ├── signals/
│   │   └── [id].js            # Signal details
│   ├── market/
│   │   └── prices.js          # Price checker
│   ├── community/
│   │   └── guides.js          # User guides
│   └── auth/
│       └── callback.js        # Discord OAuth callback
├── components/
│   ├── reviews/
│   │   ├── ReviewList.jsx     # Display reviews
│   │   ├── ReviewForm.jsx     # Submit review
│   │   └── StarRating.jsx     # 5-star UI
│   ├── comments/
│   │   ├── CommentThread.jsx  # Nested comments
│   │   ├── CommentForm.jsx    # Post/reply
│   │   └── VoteButtons.jsx    # Upvote/downvote
│   ├── traders/
│   │   ├── TraderCard.jsx     # Trader preview
│   │   └── SubscribeButton.jsx # Stripe checkout
│   └── shared/
│       ├── Navbar.jsx
│       └── Footer.jsx
└── package.json
```

---

## 🔥 Interactive Features (Key Selling Points)

### 1. **Review System** (`/api/reviews`)

**Features:**
- 5-star rating with optional text review
- Title + detailed feedback
- Vote on reviews (helpful/unhelpful)
- Auto-calculates avg rating
- Sort by: Top rated, Recent, Rating high/low

**Usage:**
```javascript
// Post a review
POST /api/reviews
{
  "reviewableType": "trader",
  "reviewableId": 1,
  "rating": 5,
  "title": "Best trader I've followed!",
  "reviewText": "Made 2M coins in 3 weeks..."
}

// Get reviews for a trader
GET /api/reviews/trader/1?sort=helpful&limit=20

// Vote on review
POST /api/reviews/123/vote
{
  "voteType": "helpful"
}
```

### 2. **Comments System** (`/api/comments`)

**Features:**
- Nested/threaded comments (unlimited depth)
- Upvote/downvote on comments
- Edit with "edited" flag
- Soft delete (maintains structure)
- Pin important comments (traders only)
- Real-time reply counts

**Usage:**
```javascript
// Post comment
POST /api/comments
{
  "commentableType": "signal",
  "commentableId": 45,
  "commentText": "Great call! Made 85k profit",
  "parentCommentId": null  // or ID to reply
}

// Vote on comment
POST /api/comments/123/vote
{
  "voteType": "upvote"
}

// Pin comment (traders only)
POST /api/comments/123/pin
```

### 3. **Voting System**

Unified voting across platform:
- **Comments**: Upvote/downvote (Reddit-style)
- **Reviews**: Helpful/unhelpful (Amazon-style)
- **Community content**: Upvote/downvote

**Database:**
```sql
CREATE TABLE votes (
  user_id INTEGER,
  votable_type VARCHAR(50),  -- 'comment', 'review', 'guide'
  votable_id INTEGER,
  vote_type VARCHAR(10),     -- 'upvote', 'downvote', 'helpful', 'unhelpful'
  UNIQUE (user_id, votable_type, votable_id)
)
```

---

## 💰 Monetization Flow

### Trader Subscriptions

1. **Trader sets price**: £9.99/month
2. **User subscribes**: Stripe checkout
3. **Platform takes 25%**: £2.50
4. **Trader keeps 75%**: £7.49
5. **Auto-renewal**: Monthly billing

### One-Off Content

1. **Trader uploads**: PDF guide, price £19.99
2. **User purchases**: One-time payment
3. **Platform takes 25%**: £5.00
4. **Trader keeps 75%**: £14.99
5. **User owns forever**: Download anytime

### Revenue Calculation

**Example: 50 traders, 5,000 users**
- 20 traders avg £500/mo subscriptions = £10,000
- Platform 25% = **£2,500/month**
- 50 traders sell avg £200/mo content = £10,000
- Platform 25% = **£2,500/month**
- **Total: £5,000/month = £60k/year**

---

## 🔒 Authentication Flow

### Discord OAuth

1. User clicks "Login with Discord"
2. Redirects to Discord OAuth
3. Discord returns with code
4. Backend exchanges code for tokens
5. Fetch user info from Discord API
6. Create/update user in database
7. Issue JWT token
8. Return to frontend with JWT

**Environment Variables:**
```env
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_secret
DISCORD_REDIRECT_URI=http://localhost:3001/api/auth/discord/callback
JWT_SECRET=your_jwt_secret
```

---

## 📈 Price Scraping

### Futbin Scraper

**Strategy:**
1. Scrape Futbin every 5-10 minutes
2. Cache prices in PostgreSQL
3. Track 24h price changes
4. Alert users when targets hit

**Implementation:**
```javascript
// services/scraper.js
async function scrapeFutbinPrice(cardName, cardRating) {
  const url = `https://www.futbin.com/26/player/${cardId}`;
  const html = await axios.get(url);
  const $ = cheerio.load(html.data);

  return {
    ps_price: $('.ps-price').text(),
    xbox_price: $('.xbox-price').text(),
    pc_price: $('.pc-price').text()
  };
}
```

**Cron Job:**
```javascript
// Update prices every 5 minutes
setInterval(async () => {
  const popularCards = await getPopularCards();
  for (const card of popularCards) {
    const prices = await scrapeFutbinPrice(card.name, card.rating);
    await savePrices(card, prices);
    await checkPriceAlerts(card, prices);
  }
}, 5 * 60 * 1000);
```

---

## 🚀 Deployment

### Prerequisites
- PostgreSQL 14+
- Node.js 18+
- Redis (for caching)
- AWS S3 (for file uploads)

### Environment Setup

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fut_hub
DB_USER=postgres
DB_PASSWORD=your_password

# Discord OAuth
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_REDIRECT_URI=

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# JWT
JWT_SECRET=

# AWS S3
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_BUCKET_NAME=

# Frontend
FRONTEND_URL=http://localhost:3000
```

### Installation

```bash
# Clone repo
git clone https://github.com/yourusername/fut-hub.git
cd fut-hub

# Backend
cd backend
npm install
npm run migrate  # Run database migrations
npm run seed     # Optional: Seed test data
npm start

# Frontend
cd ../frontend
npm install
npm run dev
```

### Production Deployment

**Backend (Railway/Render):**
1. Connect GitHub repo
2. Set environment variables
3. Deploy main branch
4. Scale as needed

**Frontend (Vercel):**
1. Import Next.js project
2. Set NEXT_PUBLIC_API_URL
3. Deploy

**Database (Supabase/RDS):**
1. Create PostgreSQL instance
2. Run migrations
3. Configure connection pooling

---

## 📱 API Documentation

### Authentication

```
POST /api/auth/discord
GET  /api/auth/discord/callback
POST /api/auth/logout
GET  /api/auth/me
```

### Traders

```
GET    /api/traders              # Browse traders
GET    /api/traders/:id          # Get trader profile
POST   /api/traders              # Create trader profile (auth required)
PUT    /api/traders/:id          # Update profile (auth required)
GET    /api/traders/:id/signals  # Get trader's signals
GET    /api/traders/:id/stats    # Get performance stats
```

### Signals

```
GET    /api/signals              # Browse signals (free + premium if subscribed)
GET    /api/signals/:id          # Get signal details
POST   /api/signals              # Create signal (traders only)
PUT    /api/signals/:id          # Update signal (traders only)
POST   /api/signals/:id/close    # Close signal with result (traders only)
POST   /api/signals/:id/invest   # Mark "I invested" (users)
```

### Reviews

```
GET    /api/reviews/:type/:id    # Get reviews (type: trader/content/signal)
POST   /api/reviews              # Create review (auth required)
PUT    /api/reviews/:id          # Update review (auth required)
DELETE /api/reviews/:id          # Delete review (auth required)
POST   /api/reviews/:id/vote     # Vote helpful/unhelpful (auth required)
```

### Comments

```
GET    /api/comments/:type/:id   # Get comments (nested)
POST   /api/comments             # Post comment (auth required)
PUT    /api/comments/:id         # Edit comment (auth required)
DELETE /api/comments/:id         # Delete comment (auth required)
POST   /api/comments/:id/vote    # Upvote/downvote (auth required)
POST   /api/comments/:id/pin     # Pin comment (traders only)
```

### Subscriptions

```
GET    /api/subscriptions/mine   # Get my subscriptions (auth required)
POST   /api/subscriptions        # Subscribe to trader (auth required)
DELETE /api/subscriptions/:id    # Cancel subscription (auth required)
POST   /api/stripe/webhook       # Stripe webhook handler
```

---

## 🎨 Frontend Components

### Review Component

```jsx
<ReviewList
  reviewableType="trader"
  reviewableId={traderId}
  sortBy="helpful"
  allowPosting={true}
/>

<ReviewForm
  reviewableType="trader"
  reviewableId={traderId}
  onSuccess={refreshReviews}
/>
```

### Comment Component

```jsx
<CommentThread
  commentableType="signal"
  commentableId={signalId}
  allowReplies={true}
  showVotes={true}
/>

<CommentForm
  commentableType="signal"
  commentableId={signalId}
  parentCommentId={null}  // or ID to reply
  onSuccess={refreshComments}
/>
```

---

## 🔮 Future Enhancements

### Phase 2
- [ ] Mobile app (React Native)
- [ ] Push notifications
- [ ] Live chat
- [ ] Trading tournaments

### Phase 3
- [ ] API access for developers
- [ ] White-label for Discord servers
- [ ] Advanced analytics dashboard
- [ ] AI price predictions

### Phase 4
- [ ] Chrome extension
- [ ] Automated trading signals
- [ ] Integration with EA API (if available)

---

## 📄 License

MIT License - See LICENSE file

---

## 🤝 Contributing

1. Fork the repo
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

---

## 💬 Support

- Discord: [Join our server](https://discord.gg/...)
- Email: support@futhub.gg
- Twitter: [@FUTHub](https://twitter.com/...)

---

**Built with ❤️ for the FUT trading community**
