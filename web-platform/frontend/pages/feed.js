import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../components/layout/Layout';
import { api } from '../lib/api';
import toast from 'react-hot-toast';

export default function Feed() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, signals, updates

  useEffect(() => {
    // Check authentication
    const token = localStorage.getItem('auth_token');
    if (!token) {
      router.push('/login');
      return;
    }

    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUser(payload);
      fetchFeed();
    } catch (error) {
      console.error('Invalid token:', error);
      localStorage.removeItem('auth_token');
      router.push('/login');
    }
  }, [filter]);

  const fetchFeed = async () => {
    try {
      setLoading(true);
      // Fetch live feed from subscribed traders
      const signalsRes = await api.getSignals({ status: 'active', limit: 20 });

      // Transform to feed items
      const feedItems = (signalsRes.data.signals || []).map(signal => ({
        id: signal.id,
        type: 'signal',
        trader: {
          id: signal.trader_id,
          username: signal.trader_username,
          avatar: signal.trader_avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'
        },
        content: signal,
        timestamp: signal.created_at
      }));

      setFeed(feedItems);
    } catch (error) {
      console.error('Failed to fetch feed:', error);
      toast.error('Failed to load feed');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Live Feed">
        <div className="min-h-screen bg-gradient-to-b from-gray-900 via-black to-gray-900 flex items-center justify-center">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-purple-500"></div>
            <p className="text-white mt-4 text-lg">Loading your exclusive feed...</p>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Live Feed - FUT Hub">
      {/* Hero Header */}
      <div className="bg-gradient-to-br from-purple-900 via-pink-900 to-purple-900 border-b border-purple-500/20">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl md:text-5xl font-black text-white mb-2">
                🔴 Live Trades Feed
              </h1>
              <p className="text-purple-200 text-lg">
                Exclusive signals from your subscribed traders
              </p>
            </div>
            <Link href="/traders">
              <button className="hidden md:block px-6 py-3 bg-gradient-to-r from-pink-500 to-purple-500 text-white rounded-xl font-bold hover:from-pink-600 hover:to-purple-600 transition-all shadow-lg hover:shadow-pink-500/50">
                Find More Traders
              </button>
            </Link>
          </div>

          {/* Filter Tabs */}
          <div className="mt-8 flex gap-3">
            <button
              onClick={() => setFilter('all')}
              className={`px-6 py-2 rounded-lg font-bold transition-all ${
                filter === 'all'
                  ? 'bg-white text-purple-900 shadow-lg'
                  : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              All Activity
            </button>
            <button
              onClick={() => setFilter('signals')}
              className={`px-6 py-2 rounded-lg font-bold transition-all ${
                filter === 'signals'
                  ? 'bg-white text-purple-900 shadow-lg'
                  : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              Signals Only
            </button>
            <button
              onClick={() => setFilter('updates')}
              className={`px-6 py-2 rounded-lg font-bold transition-all ${
                filter === 'updates'
                  ? 'bg-white text-purple-900 shadow-lg'
                  : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              Updates
            </button>
          </div>
        </div>
      </div>

      {/* Feed Content */}
      <div className="min-h-screen bg-gradient-to-b from-black via-gray-900 to-black">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {feed.length === 0 ? (
            <div className="text-center py-20">
              <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-2xl p-12 border border-gray-700">
                <span className="text-7xl mb-6 block">📭</span>
                <h3 className="text-2xl font-bold text-white mb-4">
                  Your Feed is Empty
                </h3>
                <p className="text-gray-400 mb-8 max-w-md mx-auto">
                  Subscribe to elite traders to see their exclusive signals and updates in your personalized feed
                </p>
                <Link href="/traders">
                  <button className="px-8 py-4 bg-gradient-to-r from-pink-500 to-purple-500 text-white rounded-xl font-bold hover:from-pink-600 hover:to-purple-600 transition-all shadow-lg hover:shadow-pink-500/50">
                    Discover Elite Traders
                  </button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {feed.map(item => (
                <div
                  key={`${item.type}-${item.id}`}
                  className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-purple-500/20 overflow-hidden hover:border-purple-500/40 transition-all shadow-xl hover:shadow-2xl hover:shadow-purple-500/20"
                >
                  {/* Trader Header */}
                  <div className="p-6 border-b border-gray-800">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <img
                          src={item.trader.avatar}
                          alt={item.trader.username}
                          onClick={() => router.push(`/traders/${item.trader.id}`)}
                          className="w-12 h-12 rounded-full border-2 border-purple-500 cursor-pointer hover:scale-110 transition-transform"
                        />
                        <div>
                          <h3
                            onClick={() => router.push(`/traders/${item.trader.id}`)}
                            className="font-bold text-white text-lg cursor-pointer hover:text-purple-400 transition-colors"
                          >
                            {item.trader.username}
                          </h3>
                          <p className="text-sm text-gray-400">
                            {new Date(item.timestamp).toLocaleString()}
                          </p>
                        </div>
                      </div>

                      {item.type === 'signal' && (
                        <div className="px-4 py-2 bg-gradient-to-r from-pink-500/20 to-purple-500/20 border border-pink-500/50 rounded-full">
                          <span className="text-pink-400 font-bold text-sm">🔴 NEW SIGNAL</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Signal Content */}
                  {item.type === 'signal' && (
                    <div
                      onClick={() => router.push(`/signals/${item.content.id}`)}
                      className="p-6 cursor-pointer hover:bg-white/5 transition-colors"
                    >
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Player Card */}
                        <div className="bg-gradient-to-br from-purple-900/30 to-pink-900/30 rounded-xl p-6 border border-purple-500/20">
                          <div className="flex items-center gap-4 mb-4">
                            <img
                              src={item.content.player_image || '/default-player.png'}
                              alt={item.content.player_name}
                              className="w-24 h-24 object-contain"
                            />
                            <div>
                              <h2 className="text-2xl font-black text-white mb-2">
                                {item.content.player_name}
                              </h2>
                              <div className={`inline-block px-4 py-1 rounded-full text-xs font-bold ${
                                item.content.status === 'active' ? 'bg-green-500 text-white' :
                                item.content.status === 'closed' ? 'bg-gray-500 text-white' :
                                'bg-yellow-500 text-black'
                              }`}>
                                {item.content.status?.toUpperCase()}
                              </div>
                            </div>
                          </div>

                          {item.content.notes && (
                            <div className="bg-black/30 rounded-lg p-4 mt-4">
                              <p className="text-sm text-gray-300">{item.content.notes}</p>
                            </div>
                          )}
                        </div>

                        {/* Trade Details */}
                        <div className="space-y-4">
                          <div className="bg-gradient-to-br from-blue-900/50 to-blue-800/50 rounded-xl p-4 border border-blue-500/30">
                            <div className="text-xs text-blue-300 mb-1 font-semibold">BUY PRICE</div>
                            <div className="text-3xl font-black text-white">
                              {item.content.entry_price_min}
                              {item.content.entry_price_max ? ` - ${item.content.entry_price_max}` : ''}
                            </div>
                            <div className="text-xs text-blue-200 mt-1">coins</div>
                          </div>

                          {item.content.sell_price && (
                            <div className="bg-gradient-to-br from-green-900/50 to-green-800/50 rounded-xl p-4 border border-green-500/30">
                              <div className="text-xs text-green-300 mb-1 font-semibold">TARGET PRICE</div>
                              <div className="text-3xl font-black text-white">
                                {item.content.sell_price}
                              </div>
                              <div className="text-xs text-green-200 mt-1">coins</div>
                            </div>
                          )}

                          {item.content.roi !== null && (
                            <div className={`bg-gradient-to-br rounded-xl p-4 border ${
                              Number(item.content.roi) > 0
                                ? 'from-green-900/50 to-emerald-800/50 border-green-500/30'
                                : 'from-red-900/50 to-rose-800/50 border-red-500/30'
                            }`}>
                              <div className={`text-xs mb-1 font-semibold ${
                                Number(item.content.roi) > 0 ? 'text-green-300' : 'text-red-300'
                              }`}>
                                RETURN ON INVESTMENT
                              </div>
                              <div className={`text-4xl font-black ${
                                Number(item.content.roi) > 0 ? 'text-green-400' : 'text-red-400'
                              }`}>
                                {Number(item.content.roi) > 0 ? '+' : ''}{Number(item.content.roi).toFixed(1)}%
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="mt-6 pt-6 border-t border-gray-800 flex items-center justify-between">
                        <div className="flex items-center gap-6 text-gray-400">
                          <span className="flex items-center gap-2">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                            {item.content.view_count || 0} views
                          </span>
                        </div>

                        <button className="px-6 py-2 bg-gradient-to-r from-pink-500 to-purple-500 text-white rounded-lg font-bold hover:from-pink-600 hover:to-purple-600 transition-all">
                          View Full Details →
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
