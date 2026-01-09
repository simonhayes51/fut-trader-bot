/**
 * Seed Database with Test Data
 * Run this to add sample traders and signals
 */

const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.DB_HOST,
  port: process.env.DB_PORT,
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
});

async function seed() {
  console.log('🌱 Seeding database with test data...');

  try {
    // Clear existing data (optional - comment out if you want to keep existing data)
    console.log('Cleaning existing data...');
    await pool.query('TRUNCATE users, trader_profiles, signals, subscriptions, reviews, comments RESTART IDENTITY CASCADE');

    // Insert test users
    console.log('Creating test users...');
    const users = await pool.query(`
      INSERT INTO users (discord_id, username, avatar_url, is_trader, is_verified_trader)
      VALUES
        ('1001', 'FUTWolf', 'https://cdn.discordapp.com/embed/avatars/0.png', TRUE, TRUE),
        ('1002', 'CoinMaster', 'https://cdn.discordapp.com/embed/avatars/1.png', TRUE, TRUE),
        ('1003', 'TradingKing', 'https://cdn.discordapp.com/embed/avatars/2.png', TRUE, FALSE),
        ('1004', 'IconFlip', 'https://cdn.discordapp.com/embed/avatars/3.png', TRUE, TRUE),
        ('1005', 'MetaTrader', 'https://cdn.discordapp.com/embed/avatars/4.png', TRUE, FALSE),
        ('2001', 'JohnDoe', 'https://cdn.discordapp.com/embed/avatars/5.png', FALSE, FALSE)
      RETURNING id, username
    `);

    console.log(`✅ Created ${users.rows.length} users`);

    // Insert trader profiles
    console.log('Creating trader profiles...');
    const traders = await pool.query(`
      INSERT INTO trader_profiles (
        user_id, display_name, bio, specialties,
        subscription_price_monthly, is_accepting_subscribers,
        total_signals, winning_signals, losing_signals,
        win_rate, avg_roi, avg_rating, total_reviews, total_subscribers
      )
      VALUES
        (1, 'FUTWolf', 'Icon trading specialist with 5+ years experience. Focus on weekend flips and long-term investments.',
         ARRAY['Icons', 'Meta Cards', 'Weekend Flips'], 9.99, TRUE, 45, 32, 13, 71.11, 18.50, 4.8, 24, 156),

        (2, 'CoinMaster', 'Fodder and special card expert. Daily signals with 75%+ win rate. Fast flips for quick profits!',
         ARRAY['Fodder', 'Special Cards', 'Quick Flips'], 14.99, TRUE, 89, 71, 18, 79.78, 22.30, 4.9, 67, 342),

        (3, 'TradingKing', 'Meta player trader focusing on usable cards. Low risk, steady profits. Perfect for beginners.',
         ARRAY['Meta Cards', 'Usable Players', 'Low Risk'], 4.99, TRUE, 23, 18, 5, 78.26, 15.20, 4.5, 12, 89),

        (4, 'IconFlip', 'Icon investment specialist. Long-term holds with massive returns. Premium tier available.',
         ARRAY['Icons', 'Long Term', 'High Return'], 19.99, TRUE, 34, 28, 6, 82.35, 35.80, 4.7, 41, 203),

        (5, 'MetaTrader', 'FIFA competitive player turned trader. Expert in meta shifts and promo predictions.',
         ARRAY['Meta Analysis', 'Promos', 'Content Predictions'], 7.99, TRUE, 56, 39, 17, 69.64, 16.70, 4.3, 19, 124)
      RETURNING id, display_name
    `);

    console.log(`✅ Created ${traders.rows.length} trader profiles`);

    // Insert signals
    console.log('Creating trading signals...');
    const signals = await pool.query(`
      INSERT INTO signals (
        trader_id, card_name, card_rating, card_position,
        signal_type, is_premium, entry_price_min, entry_price_max,
        target_price, time_frame, risk_level, confidence_level,
        reasoning, status, result, roi, views, likes, invested_count
      )
      VALUES
        -- Active signals
        (1, 'Kylian Mbappé', 91, 'ST', 'BUY', FALSE, 285000, 295000, 340000, '3-5 days', 'Medium', 85,
         'TOTY around the corner. Supply low, demand rising. Easy 15-20% profit incoming.', 'active', NULL, NULL, 234, 45, 67),

        (2, 'Cristiano Ronaldo', 90, 'ST', 'BUY', TRUE, 125000, 135000, 165000, 'Quick flip', 'Low', 90,
         'Weekend League demand spike expected. Buy Thursday, sell Friday night.', 'active', NULL, NULL, 189, 38, 52),

        (4, 'Pelé', 95, 'CAM', 'BUY', TRUE, 2100000, 2200000, 2500000, 'Long term', 'Low', 95,
         'Icon SBCs coming next month. Prime Pelé will skyrocket. Hold for 3+ weeks.', 'active', NULL, NULL, 156, 34, 41),

        -- Closed winning signals
        (1, 'Erling Haaland', 91, 'ST', 'BUY', FALSE, 178000, 185000, 215000, '2-3 days', 'Low', 88,
         'Supply crash after rewards. Will recover before weekend.', 'closed', 'win', 21.5, 445, 89, 123),

        (2, 'Fodder 84-86 Rated', 84, 'ANY', 'BUY', FALSE, 4500, 5000, 7000, '1 week', 'Low', 95,
         'Icon SBC released tomorrow. Fodder always spikes 40-50%.', 'closed', 'win', 45.2, 678, 156, 234),

        (3, 'Vinícius Jr', 90, 'LW', 'BUY', FALSE, 245000, 255000, 290000, 'Quick flip', 'Medium', 82,
         'Meta card, good links. Weekend League demand incoming.', 'closed', 'win', 18.7, 389, 67, 98),

        (4, 'Thierry Henry', 93, 'ST', 'BUY', TRUE, 1850000, 1900000, 2200000, 'Long term', 'Medium', 80,
         'Icon SBC requirements leaked. Henry perfect rating.', 'closed', 'win', 28.3, 267, 45, 67),

        (5, 'Casemiro', 89, 'CDM', 'BUY', FALSE, 45000, 48000, 62000, '3-5 days', 'Low', 85,
         'Strong links to meta players. Underpriced right now.', 'closed', 'win', 22.1, 312, 54, 89),

        -- Closed losing signals
        (3, 'Neymar Jr', 89, 'LW', 'BUY', FALSE, 189000, 195000, 230000, '1 week', 'High', 75,
         'Expected content boost. Did not materialize.', 'closed', 'loss', -8.3, 234, 23, 45),

        (5, 'Luka Modrić', 88, 'CM', 'BUY', FALSE, 67000, 72000, 85000, '2-3 days', 'Medium', 78,
         'Market crash was deeper than expected.', 'closed', 'loss', -6.7, 198, 18, 34)
      RETURNING id, card_name
    `);

    console.log(`✅ Created ${signals.rows.length} signals`);

    // Insert some reviews
    console.log('Creating reviews...');
    await pool.query(`
      INSERT INTO reviews (user_id, reviewable_type, reviewable_id, rating, title, review_text, helpful_count)
      VALUES
        (6, 'trader', 1, 5, 'Best trader I have followed!', 'FUTWolf consistently delivers. Made 2M coins in 3 weeks following his signals. Communication is excellent and he always updates exit prices quickly.', 45),
        (6, 'trader', 2, 5, 'Insane win rate', 'CoinMaster is the real deal. 80%+ win rate is no joke. Signals are clear and profitable. Worth every penny!', 67),
        (6, 'trader', 3, 4, 'Good for beginners', 'TradingKing has safe, reliable signals. Not the highest profits but very consistent. Great if you are new to trading.', 23),
        (6, 'trader', 4, 5, 'Icon expert', 'IconFlip knows icons inside out. His long-term calls are amazing. Made 500k profit on one Pelé investment!', 41),
        (6, 'trader', 5, 4, 'Solid content predictions', 'MetaTrader is great at predicting market shifts. Some signals miss but overall profitable.', 19)
    `);

    console.log('✅ Created reviews');

    // Insert some comments
    console.log('Creating comments...');
    await pool.query(`
      INSERT INTO comments (user_id, commentable_type, commentable_id, comment_text, upvotes)
      VALUES
        (6, 'signal', 1, 'Just bought 3 Mbappés at 287k. Let us see how this plays out!', 12),
        (6, 'signal', 2, 'Ronaldo already up to 145k! Easy profit, thanks!', 23),
        (6, 'signal', 4, 'Haaland call was perfect. Sold at 218k for 22% profit 💰', 45),
        (6, 'signal', 5, 'Fodder is flying! Already at 7.2k, massive W', 67)
    `);

    console.log('✅ Created comments');

    console.log('\n🎉 Database seeded successfully!');
    console.log('\n📊 Summary:');
    console.log('  - 6 users created');
    console.log('  - 5 trader profiles created');
    console.log('  - 10 trading signals created');
    console.log('  - 5 reviews created');
    console.log('  - 4 comments created');
    console.log('\n✨ Your platform now has test data to display!');

  } catch (error) {
    console.error('❌ Seed failed:', error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

// Run seed
seed();
