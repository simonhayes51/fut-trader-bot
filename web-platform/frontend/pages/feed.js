import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { api } from '../lib/api';
import toast from 'react-hot-toast';
import Sidebar from '../components/layout/Sidebar';
import StoriesRow from '../components/StoriesRow';
import Achievements from '../components/Achievements';
import PortfolioWidget from '../components/PortfolioWidget';

export default function Feed() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [newPostsAvailable, setNewPostsAvailable] = useState(3);

  useEffect(() => {
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
      const signalsRes = await api.getSignals({ status: 'active', limit: 20 });

      const feedItems = (signalsRes.data.signals || []).map(signal => ({
        id: signal.id,
        type: 'trade',
        trader: {
          id: signal.trader_id,
          username: signal.trader_username || 'Unknown Trader',
          avatar: signal.trader_avatar || 'https://cdn.discordapp.com/embed/avatars/1.png',
          badge: 'Quick Flip', // This should come from signal.trade_type
          badgeColor: 'bg-orange-500'
        },
        content: signal,
        timestamp: signal.created_at,
        timeAgo: '5 min ago' // Calculate this properly
      }));

      setFeed(feedItems);
    } catch (error) {
      console.error('Failed to fetch feed:', error);
      toast.error('Failed to load feed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-black">
      {/* Left Sidebar */}
      <Sidebar />

      {/* Main Feed Area */}
      <div className="flex-1 ml-64 mr-96 min-h-screen">
        <div className="max-w-4xl mx-auto p-6 space-y-6">
          {/* Stories Row */}
          <StoriesRow />

          {/* Achievements */}
          <Achievements />

          {/* Feed Header */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-black text-white mb-1">Your Feed</h1>
                <p className="text-gray-400">Latest tips from your traders</p>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setFilter('all')}
                  className={`px-6 py-2 rounded-xl font-semibold transition-all ${
                    filter === 'all'
                      ? 'bg-cyan-500 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => setFilter('trades')}
                  className={`px-6 py-2 rounded-xl font-semibold transition-all ${
                    filter === 'trades'
                      ? 'bg-cyan-500 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  }`}
                >
                  Trades
                </button>
                <button
                  onClick={() => setFilter('predictions')}
                  className={`px-6 py-2 rounded-xl font-semibold transition-all ${
                    filter === 'predictions'
                      ? 'bg-cyan-500 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  }`}
                >
                  Predictions
                </button>
                <button className="p-2 bg-gray-800 rounded-xl text-gray-400 hover:bg-gray-700 transition-all">
                  🔽
                </button>
              </div>
            </div>

            {/* New Posts Available Banner */}
            {newPostsAvailable > 0 && (
              <button
                onClick={() => {
                  fetchFeed();
                  setNewPostsAvailable(0);
                }}
                className="w-full bg-gradient-to-r from-cyan-900 to-cyan-800 border border-cyan-500/50 rounded-xl p-4 text-cyan-400 font-semibold flex items-center justify-center gap-2 hover:from-cyan-800 hover:to-cyan-700 transition-all"
              >
                <span className="text-lg">✨</span>
                <span>{newPostsAvailable} new posts available</span>
              </button>
            )}
          </div>

          {/* Feed Posts */}
          {loading ? (
            <div className="text-center py-20">
              <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-cyan-500"></div>
            </div>
          ) : feed.length === 0 ? (
            <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-gray-800 p-20 text-center">
              <span className="text-7xl mb-4 block">📭</span>
              <h3 className="text-2xl font-bold text-white mb-4">Your Feed is Empty</h3>
              <p className="text-gray-400 mb-8">Subscribe to traders to see their exclusive content</p>
              <button
                onClick={() => router.push('/traders')}
                className="px-8 py-4 bg-gradient-to-r from-cyan-500 to-cyan-600 text-white rounded-xl font-bold hover:from-cyan-600 hover:to-cyan-700 transition-all"
              >
                Discover Traders
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {feed.map(item => (
                <div
                  key={item.id}
                  className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-gray-800 hover:border-gray-700 transition-all overflow-hidden"
                >
                  {/* Post Header */}
                  <div className="p-6 border-b border-gray-800">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <img
                          src={item.trader.avatar}
                          alt={item.trader.username}
                          onClick={() => router.push(`/traders/${item.trader.id}`)}
                          className="w-12 h-12 rounded-full border-2 border-cyan-500 cursor-pointer hover:scale-110 transition-transform"
                        />
                        <div>
                          <div className="flex items-center gap-2">
                            <h3
                              onClick={() => router.push(`/traders/${item.trader.id}`)}
                              className="font-bold text-white cursor-pointer hover:text-cyan-400 transition-colors"
                            >
                              {item.trader.username}
                            </h3>
                            <div className={`${item.trader.badgeColor} text-white text-[10px] font-black px-2 py-0.5 rounded-full`}>
                              {item.trader.badge}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>⏱️</span>
                            <span>{item.timeAgo}</span>
                          </div>
                        </div>
                      </div>

                      <button className="text-gray-500 hover:text-white transition-colors">
                        ⋮
                      </button>
                    </div>
                  </div>

                  {/* Post Content */}
                  <div
                    onClick={() => router.push(`/signals/${item.content.id}`)}
                    className="p-6 cursor-pointer hover:bg-gray-900/50 transition-colors"
                  >
                    <div className="flex items-center gap-4 mb-4">
                      <span className="text-2xl">🚨</span>
                      <p className="text-white font-semibold">
                        QUICK FLIP ALERT! {item.content.player_name || item.content.card_name} is about to spike due to upcoming SBC requirements.
                        Get in NOW before it's too late. This is a time-sensitive opportunity!
                      </p>
                    </div>

                    {/* Player Card/Image would go here */}
                    {item.content.player_image && (
                      <div className="mb-4 rounded-xl overflow-hidden">
                        <img
                          src={item.content.player_image}
                          alt={item.content.player_name}
                          className="w-full max-h-96 object-cover"
                        />
                      </div>
                    )}

                    {/* Trade Stats */}
                    <div className="grid grid-cols-3 gap-4">
                      <div className="bg-cyan-500/10 border border-cyan-500/20 rounded-xl p-4 text-center">
                        <div className="text-xs text-cyan-400 mb-1">BUY</div>
                        <div className="text-xl font-black text-white">
                          {item.content.entry_price_min}
                        </div>
                      </div>
                      {item.content.sell_price && (
                        <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4 text-center">
                          <div className="text-xs text-green-400 mb-1">SELL</div>
                          <div className="text-xl font-black text-white">
                            {item.content.sell_price}
                          </div>
                        </div>
                      )}
                      {item.content.roi !== null && (
                        <div className={`rounded-xl p-4 text-center ${
                          Number(item.content.roi) > 0
                            ? 'bg-green-500/10 border border-green-500/20'
                            : 'bg-red-500/10 border border-red-500/20'
                        }`}>
                          <div className={`text-xs mb-1 ${
                            Number(item.content.roi) > 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            ROI
                          </div>
                          <div className={`text-xl font-black ${
                            Number(item.content.roi) > 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {Number(item.content.roi) > 0 ? '+' : ''}{Number(item.content.roi).toFixed(1)}%
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Post Actions */}
                  <div className="px-6 py-4 border-t border-gray-800 flex items-center justify-between">
                    <div className="flex gap-6">
                      <button className="flex items-center gap-2 text-gray-400 hover:text-cyan-400 transition-colors">
                        <span>👍</span>
                        <span className="text-sm font-medium">124</span>
                      </button>
                      <button className="flex items-center gap-2 text-gray-400 hover:text-cyan-400 transition-colors">
                        <span>💬</span>
                        <span className="text-sm font-medium">23</span>
                      </button>
                      <button className="flex items-center gap-2 text-gray-400 hover:text-cyan-400 transition-colors">
                        <span>🔁</span>
                        <span className="text-sm font-medium">Share</span>
                      </button>
                    </div>
                    <button className="flex items-center gap-2 text-gray-400 hover:text-cyan-400 transition-colors">
                      <span>🔖</span>
                      <span className="text-sm font-medium">Save</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right Sidebar - Portfolio */}
      <div className="fixed right-0 top-0 w-96 h-screen p-6 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
        <PortfolioWidget />
      </div>
    </div>
  );
}
