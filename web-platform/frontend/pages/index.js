import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../components/layout/Layout';
import { api } from '../lib/api';
import StarRating from '../components/reviews/StarRating';

export default function Home() {
  const router = useRouter();
  const [topTraders, setTopTraders] = useState([]);
  const [recentSignals, setRecentSignals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [tradersRes, signalsRes] = await Promise.all([
        api.getTraders({ sort: 'top', limit: 6 }),
        api.getSignals({ sort: 'recent', limit: 6, status: 'active' })
      ]);

      setTopTraders(tradersRes.data.traders || []);
      setRecentSignals(signalsRes.data.signals || []);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="FUT Hub - The OnlyFans of FUT Trading">
      {/* Hero Section with Pitch Theme */}
      <div className="relative bg-gradient-to-br from-green-700 via-green-600 to-emerald-700 text-white overflow-hidden">
        {/* Pitch Pattern Overlay */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: `repeating-linear-gradient(
              0deg,
              transparent,
              transparent 50px,
              rgba(255,255,255,0.1) 50px,
              rgba(255,255,255,0.1) 51px
            )`,
          }}></div>
        </div>

        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent"></div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 md:py-32">
          <div className="text-center">
            <div className="inline-flex items-center gap-2 px-5 py-2 bg-yellow-400 rounded-full mb-6 shadow-lg">
              <span className="text-2xl">⚽</span>
              <span className="text-gray-900 font-bold text-sm">EXCLUSIVE TRADING PLATFORM</span>
            </div>

            <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
              Subscribe to Elite<br />
              <span className="text-yellow-400 drop-shadow-lg">
                FUT Traders
              </span>
            </h1>

            <p className="text-xl md:text-2xl mb-10 text-green-100 max-w-3xl mx-auto font-medium">
              Unlock exclusive signals, insider tips, and premium content from verified FUT traders.
              Your VIP pass to trading profits.
            </p>

            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <Link href="/traders">
                <button className="group px-10 py-5 bg-yellow-400 text-gray-900 rounded-xl font-black text-lg hover:bg-yellow-300 transition-all shadow-2xl hover:shadow-yellow-400/50 hover:scale-105 transform">
                  🔥 Browse Elite Traders
                  <span className="inline-block ml-2 group-hover:translate-x-1 transition-transform">→</span>
                </button>
              </Link>
              <Link href="/login">
                <button className="px-10 py-5 bg-white/10 backdrop-blur-md text-white rounded-xl font-bold text-lg hover:bg-white/20 transition-all border-2 border-white/30 shadow-xl">
                  Get Started Free
                </button>
              </Link>
            </div>

            {/* Live Stats */}
            <div className="mt-20 grid grid-cols-3 gap-8 max-w-4xl mx-auto">
              <div className="text-center p-6 bg-white/10 backdrop-blur-md rounded-2xl border border-white/20">
                <div className="text-5xl md:text-6xl font-black mb-2 text-yellow-400">2.5K+</div>
                <div className="text-green-100 font-semibold">Elite Traders</div>
              </div>
              <div className="text-center p-6 bg-white/10 backdrop-blur-md rounded-2xl border border-white/20">
                <div className="text-5xl md:text-6xl font-black mb-2 text-yellow-400">92%</div>
                <div className="text-green-100 font-semibold">Win Rate</div>
              </div>
              <div className="text-center p-6 bg-white/10 backdrop-blur-md rounded-2xl border border-white/20">
                <div className="text-5xl md:text-6xl font-black mb-2 text-yellow-400">50M+</div>
                <div className="text-green-100 font-semibold">Coins Made</div>
              </div>
            </div>
          </div>
        </div>

        {/* Wave Divider */}
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M0 0L60 10C120 20 240 40 360 46.7C480 53 600 47 720 43.3C840 40 960 40 1080 46.7C1200 53 1320 67 1380 73.3L1440 80V120H1380C1320 120 1200 120 1080 120C960 120 840 120 720 120C600 120 480 120 360 120C240 120 120 120 60 120H0V0Z" fill="#F9FAFB"/>
          </svg>
        </div>
      </div>

      {/* Featured Traders Section */}
      <div className="bg-gray-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-12">
            <div>
              <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-2">
                💎 Featured Traders
              </h2>
              <p className="text-xl text-gray-600">Subscribe for exclusive access to their signals</p>
            </div>
            <Link href="/traders">
              <span className="hidden md:inline-block px-6 py-3 bg-green-600 text-white rounded-xl font-bold hover:bg-green-700 transition-colors cursor-pointer shadow-lg">
                View All →
              </span>
            </Link>
          </div>

          {loading ? (
            <div className="text-center py-20">
              <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-600"></div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {topTraders.slice(0, 6).map(trader => (
                <div
                  key={trader.id}
                  onClick={() => router.push(`/traders/${trader.id}`)}
                  className="group bg-white rounded-2xl shadow-xl hover:shadow-2xl transition-all cursor-pointer overflow-hidden border-2 border-gray-100 hover:border-green-500 hover:-translate-y-2 transform"
                >
                  {/* Trader Header */}
                  <div className="relative bg-gradient-to-br from-green-600 to-emerald-600 p-6 pb-20">
                    <div className="absolute top-4 right-4">
                      {trader.is_verified_trader && (
                        <div className="bg-yellow-400 text-gray-900 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1">
                          ✓ VERIFIED
                        </div>
                      )}
                    </div>

                    <div className="relative z-10">
                      <img
                        src={trader.avatar_url || '/default-avatar.png'}
                        alt={trader.username}
                        className="w-24 h-24 rounded-full border-4 border-white shadow-2xl mx-auto mb-4 group-hover:scale-110 transition-transform"
                      />
                      <h3 className="text-2xl font-bold text-white text-center mb-1">
                        {trader.username}
                      </h3>
                      <div className="flex items-center justify-center gap-2">
                        <StarRating rating={trader.avg_rating || 0} size="sm" />
                        <span className="text-white/90 text-sm font-medium">
                          ({trader.review_count || 0})
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Stats Grid */}
                  <div className="px-6 -mt-12 relative z-20 mb-6">
                    <div className="grid grid-cols-3 gap-3">
                      <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl p-4 text-center shadow-lg">
                        <div className="text-2xl font-black text-white">
                          {trader.win_rate ? Number(trader.win_rate).toFixed(0) : 0}%
                        </div>
                        <div className="text-xs text-white/90 font-semibold mt-1">Win Rate</div>
                      </div>
                      <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-4 text-center shadow-lg">
                        <div className="text-2xl font-black text-white">
                          {trader.total_signals || 0}
                        </div>
                        <div className="text-xs text-white/90 font-semibold mt-1">Signals</div>
                      </div>
                      <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-4 text-center shadow-lg">
                        <div className="text-2xl font-black text-white">
                          {trader.total_subscribers || 0}
                        </div>
                        <div className="text-xs text-white/90 font-semibold mt-1">Subs</div>
                      </div>
                    </div>
                  </div>

                  {/* Bio */}
                  <div className="px-6 pb-6">
                    <p className="text-gray-600 text-sm mb-4 line-clamp-2 min-h-[40px]">
                      {trader.bio || 'Elite FUT trader with exclusive signals and proven results'}
                    </p>

                    {/* Subscribe Button */}
                    <div className="flex items-center justify-between pt-4 border-t border-gray-200">
                      {trader.subscription_price ? (
                        <>
                          <div>
                            <div className="text-2xl font-black text-gray-900">
                              £{Number(trader.subscription_price).toFixed(0)}
                            </div>
                            <div className="text-xs text-gray-500 font-medium">per month</div>
                          </div>
                          <button className="px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-xl font-bold hover:from-green-700 hover:to-emerald-700 transition-all shadow-lg hover:shadow-xl group-hover:scale-105 transform">
                            Subscribe
                          </button>
                        </>
                      ) : (
                        <>
                          <div className="text-2xl font-black text-green-600">FREE</div>
                          <button className="px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-xl font-bold hover:from-green-700 hover:to-emerald-700 transition-all shadow-lg hover:shadow-xl">
                            Follow
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Signals */}
      <div className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-12">
            <div>
              <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-2">
                ⚡ Latest Signals
              </h2>
              <p className="text-xl text-gray-600">Real-time trading opportunities from our pros</p>
            </div>
            <Link href="/signals">
              <span className="hidden md:inline-block px-6 py-3 bg-green-600 text-white rounded-xl font-bold hover:bg-green-700 transition-colors cursor-pointer shadow-lg">
                View All →
              </span>
            </Link>
          </div>

          {loading ? (
            <div className="text-center py-20">
              <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-600"></div>
            </div>
          ) : recentSignals.length === 0 ? (
            <div className="bg-gray-50 rounded-2xl p-16 text-center">
              <span className="text-7xl mb-4 block">⚽</span>
              <p className="text-gray-500 text-lg">No active signals at the moment</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {recentSignals.map(signal => (
                <div
                  key={signal.id}
                  onClick={() => router.push(`/signals/${signal.id}`)}
                  className="group bg-gradient-to-br from-gray-50 to-gray-100 rounded-2xl shadow-lg hover:shadow-2xl transition-all cursor-pointer overflow-hidden border-2 border-gray-200 hover:border-green-500 hover:-translate-y-1 transform"
                >
                  <div className="p-6">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4">
                      <div className={`px-4 py-2 rounded-full text-xs font-black ${
                        signal.status === 'active' ? 'bg-green-500 text-white' :
                        signal.status === 'closed' ? 'bg-gray-400 text-white' :
                        'bg-yellow-400 text-gray-900'
                      }`}>
                        🔴 {signal.status?.toUpperCase() || 'LIVE'}
                      </div>
                      {signal.roi !== null && Number(signal.roi) > 0 && (
                        <div className="px-3 py-1 bg-yellow-400 text-gray-900 rounded-full text-xs font-black">
                          🔥 HOT
                        </div>
                      )}
                    </div>

                    {/* Player Card */}
                    <div className="bg-white rounded-xl p-4 mb-4 shadow-md">
                      <div className="flex items-center gap-4">
                        <img
                          src={signal.player_image || '/default-player.png'}
                          alt={signal.player_name}
                          className="w-20 h-20 object-contain"
                        />
                        <div className="flex-1">
                          <h3 className="font-black text-lg text-gray-900 mb-1">
                            {signal.player_name}
                          </h3>
                          <p className="text-sm text-gray-600">
                            by <span className="text-green-600 font-bold">{signal.trader_username}</span>
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Price Info */}
                    <div className="grid grid-cols-2 gap-3 mb-4">
                      <div className="bg-blue-500 rounded-lg p-3 text-white">
                        <div className="text-xs font-semibold mb-1 opacity-90">BUY AT</div>
                        <div className="text-lg font-black">
                          {signal.entry_price_min}
                          {signal.entry_price_max ? `-${signal.entry_price_max}` : ''}
                        </div>
                      </div>
                      {signal.sell_price && (
                        <div className="bg-green-500 rounded-lg p-3 text-white">
                          <div className="text-xs font-semibold mb-1 opacity-90">SELL AT</div>
                          <div className="text-lg font-black">{signal.sell_price}</div>
                        </div>
                      )}
                    </div>

                    {/* ROI */}
                    {signal.roi !== null && (
                      <div className={`text-center py-3 rounded-xl font-black text-lg ${
                        Number(signal.roi) > 0
                          ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white'
                          : 'bg-gradient-to-r from-red-500 to-rose-500 text-white'
                      }`}>
                        {Number(signal.roi) > 0 ? '📈 +' : '📉 '}
                        {Number(signal.roi).toFixed(1)}% ROI
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* CTA Section */}
      <div className="relative bg-gradient-to-br from-gray-900 via-gray-800 to-black text-white py-20 overflow-hidden">
        <div className="absolute inset-0 opacity-20">
          <div className="absolute inset-0" style={{
            backgroundImage: `repeating-linear-gradient(
              45deg,
              transparent,
              transparent 50px,
              rgba(255,255,255,0.05) 50px,
              rgba(255,255,255,0.05) 51px
            )`,
          }}></div>
        </div>

        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl md:text-6xl font-black mb-6">
            Ready to Level Up Your Trading?
          </h2>
          <p className="text-xl text-gray-300 mb-10 max-w-2xl mx-auto">
            Join thousands of traders making millions in coins with exclusive signals from verified pros
          </p>
          <Link href="/traders">
            <button className="px-12 py-5 bg-gradient-to-r from-yellow-400 to-yellow-500 text-gray-900 rounded-xl font-black text-xl hover:from-yellow-300 hover:to-yellow-400 transition-all shadow-2xl hover:shadow-yellow-400/50 hover:scale-105 transform">
              ⚽ Explore Elite Traders Now
            </button>
          </Link>
        </div>
      </div>
    </Layout>
  );
}
