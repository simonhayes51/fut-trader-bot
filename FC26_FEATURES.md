# FC26 Ultimate Trading Bot - Enhanced Features

## 🎮 What's New for FC26

This bot has been completely overhauled for FC26 with tons of amazing new features!

---

## 🚀 Major Improvements

### ✅ Updated for FC26
- All API endpoints updated from FC24 to FC26
- Futbin API with rate limiting and caching
- FUT.GG integration for accurate pricing

### 🎯 Enhanced Sniping Feed
**Commands:** `/addsnipe`, `/removesnipe`, `/snipelist`

The sniping feed is now incredibly smart:
- **Smart Alerts** - Only alerts when profit opportunity exists (min 5% ROI)
- **Price Trend Analysis** - Tracks if cards are rising/falling
- **Multi-Platform** - Shows PS, Xbox, and PC prices
- **Cooldown System** - Prevents spam (5 min between alerts)
- **ROI Calculation** - Shows exact profit after EA tax
- **Customizable** - Add/remove players from tracker

**Default Tracked Players:** Mbappe, Haaland, Vini Jr, Bellingham, Salah, De Bruyne, Messi, Ronaldo, Lewandowski, Kane

### 💸 Advanced Tax Calculator
**Commands:** `/taxcalc`, `/bulktax`, `/profitscenarios`, `/targetprofit`

New features:
- **Bulk Trading** - Calculate profit for mass flipping
- **Profit Scenarios** - Visual chart showing profit at different prices
- **Target Profit** - Calculate exact sell price needed for desired profit
- **Trade Analysis** - Smart advice (🔥 Excellent, ✅ Great, ⚠️ Low profit)
- **Multiple Quantities** - Support for 1-1000 cards

### ⚖️ Player Comparison
**Command:** `/compare`

Compare two players side-by-side:
- **Full Stats** - Pace, Shooting, Passing, Dribbling, Defending, Physical
- **Winner Indicators** - ✅ marks who wins each stat
- **Price Comparison** - Shows price difference
- **Value Rating** - Coins per rating point
- **League & Nation** - Full metadata comparison

### ⚽ Squad Rating Calculator
**Commands:** `/squadrating`, `/sbcrating`, `/chemboost`

Essential tools for squad building:
- **Squad Rating** - Calculate exact squad rating from 11 players
- **SBC Helper** - Find what rating needed to reach target
- **Rating Distribution** - Shows how many 85+, 80-84, etc.
- **SBC Value** - Estimates fodder value
- **Chemistry Boost** - Calculate rating boost from chemistry

### 🔄 FC26 Evolutions System
**Commands:** `/evolutions`, `/evodetails`, `/evocalc`, `/bestevo`

Complete evolution tracking:
- **Evolution List** - View all available evolutions
- **Detailed Requirements** - Objectives, stat requirements
- **Evolution Calculator** - Check if player qualifies
- **Best Candidates** - Suggests optimal players for each evo
- **Stat Upgrades** - Shows exact boosts

**Included Evolutions:**
- Meta Evolution I (Attackers)
- Defensive Wall (Defenders)
- Playmaker Pro (Midfielders)
- Pace Demon (Wingers)

### 📊 Market Analysis & Investments
**Commands:** `/marketoverview`, `/investments`, `/marketcalendar`, `/foddercheck`

Professional trading tools:
- **Market Overview** - Current market phase and trends
- **Investment Guide** - Suggestions by budget (Budget/Medium/High)
- **Content Calendar** - Weekly/monthly schedule
- **Best Buy/Sell Times** - Optimal trading windows
- **Fodder Pricing** - Current rates for 83-89 rated cards
- **Market Phases** - Identifies if it's crash/hype/stable

---

## 📋 Complete Command List

### 💰 Trading & Prices
- `/pricecheck` - Check player prices with graphs
- `/trending` - View top risers/fallers (6h or 24h)
- `/taxcalc` - Calculate profit/loss after tax
- `/bulktax` - Calculate bulk trading profit
- `/profitscenarios` - Visualize profit scenarios
- `/targetprofit` - Find required sell price

### 🎯 Sniping & Alerts
- `/addsnipe` - Add player to sniping tracker
- `/removesnipe` - Remove player from tracker
- `/snipelist` - View tracked players
- **Auto Alerts** - Sniping feed posts opportunities automatically

### ⚖️ Player Tools
- `/compare` - Compare two players side-by-side
- `/squadrating` - Calculate squad rating
- `/sbcrating` - Find rating needed for SBC
- `/chemboost` - Calculate chemistry boost

### 🔄 Evolutions (FC26)
- `/evolutions` - List all evolutions
- `/evodetails` - Detailed evolution requirements
- `/evocalc` - Check if player qualifies
- `/bestevo` - Best players for evolution

### 📊 Market Intelligence
- `/marketoverview` - Market phase and trends
- `/investments` - Investment suggestions
- `/marketcalendar` - Content schedule
- `/foddercheck` - Fodder price guide

### 💼 Portfolio Tracking
- `/setcoins` - Set starting balance
- `/logtrade` - Log a trade
- `/checkprofit` - View profit summary
- `/saleshistory` - Recent trade history
- `/traderprofile` - Your trading stats
- `/profitgraph` - Visualize profit over time

### 🛠️ Utility
- `/ping` - Check bot latency
- `/reload` - Reload cog (Admin only)

---

## 🎯 Pro Trading Tips (Built into Bot)

### Best Times to Trade
**BUY:**
- Sunday evenings (Weekend League ends)
- Thursday morning (Rivals rewards)
- During content drops (pack openings)
- Monday mornings (lowest activity)

**SELL:**
- Friday afternoon (Weekend League hype)
- Tuesday (SBC releases)
- Before major content announcements
- Weekend mornings (peak activity)

### Investment Strategies by Budget

**Budget (<50k):**
- 83-84 rated fodder (safe, consistent)
- Position change cards (quick flips)
- Shadow/Hunter chemistry styles
- League SBC requirement players

**Medium (50k-200k):**
- 85-86 fodder (Icon SBCs)
- Meta gold cards (weekend flips)
- TOTW cards (Tuesday SBC requirement)
- Out-of-pack special cards

**High (200k+):**
- High-rated meta cards (hold value)
- Icons/Heroes (SBC fodder later)
- 87-89 fodder in bulk
- Top-tier promo cards (limited supply)

---

## 🔥 What Makes This Bot Amazing

1. **FC26 Specific** - Built for current game, not old versions
2. **Smart Alerts** - Only notifies profitable opportunities
3. **Visual Tools** - Charts and graphs for better decisions
4. **Rate Limited** - Won't get banned from APIs
5. **Cached Data** - Fast responses, reduced API calls
6. **Error Handling** - Robust and reliable
7. **Educational** - Teaches good trading habits
8. **Complete Toolkit** - Everything a trader needs

---

## 🚀 Technical Improvements

### API Updates
- Futbin API: FC24 → FC26 endpoints
- FUT.GG: Enhanced price fetching with fallbacks
- Rate limiting: 500ms between requests
- Caching: 2-minute TTL for price data

### Code Quality
- Async/await for all network operations
- Type hints throughout
- Comprehensive error handling
- Logging for debugging
- Clean cog architecture

### Performance
- Parallel API calls where possible
- Database connection pooling
- Efficient price tracking
- Smart cache invalidation

---

## 📝 Notes

- All prices are fetched from live APIs (Futbin, FUT.GG)
- Sniping alerts check every 3 minutes
- Price graphs show last 24 hours of data
- Evolution requirements based on current FC26 evolutions
- Market advice based on typical FC game cycle

---

## 🙏 Credits

**Created by:** www.futhub.co.uk
**Updated for:** FC26
**Data Sources:** Futbin, FUT.GG
**Framework:** discord.py, asyncpg, aiohttp

---

**Enjoy trading! ⚽💰**
