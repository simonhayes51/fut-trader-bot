import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../components/layout/Layout';
import { api } from '../lib/api';
import toast from 'react-hot-toast';

export default function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [subscribedTraders, setSubscribedTraders] = useState([]);
  const [recentSignals, setRecentSignals] = useState([]);
  const [loading, setLoading] = useState(true);

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
      fetchDashboardData();
    } catch (error) {
      console.error('Invalid token:', error);
      localStorage.removeItem('auth_token');
      router.push('/login');
    }
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      // Fetch subscribed traders and recent signals
      const [signalsRes] = await Promise.all([
        api.getSignals({ status: 'active', limit: 10 })
      ]);

      setRecentSignals(signalsRes.data.signals || []);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      toast.error('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Dashboard">
        <div className="min-h-screen flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Dashboard - FUT Hub">
      {/* Hero Section with FIFA Theme */}
      <div className="relative bg-gradient-to-br from-green-700 via-green-600 to-emerald-600 text-white">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: `repeating-linear-gradient(0deg, transparent, transparent 50px, rgba(255,255,255,0.1) 50px, rgba(255,255,255,0.1) 51px)`,
          }}></div>
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-extrabold mb-2">
                Welcome back, {user?.username}! ⚽
              </h1>
              <p className="text-green-100 text-lg">
                Your exclusive trading hub - track signals, manage subscriptions, and maximize profits
              </p>
            </div>
            <div className="hidden md:block">
              <img
                src={user?.avatar || '/default-avatar.png'}
                alt={user?.username}
                className="w-24 h-24 rounded-full border-4 border-white shadow-2xl"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl shadow-lg p-6 text-white">
            <div className="flex items-center justify-between mb-2">
              <span className="text-3xl">📊</span>
              <span className="text-sm opacity-80">Active</span>
            </div>
            <div className="text-3xl font-bold">{recentSignals.length}</div>
            <div className="text-blue-100 text-sm mt-1">Live Signals</div>
          </div>

          <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl shadow-lg p-6 text-white">
            <div className="flex items-center justify-between mb-2">
              <span className="text-3xl">👥</span>
              <span className="text-sm opacity-80">Following</span>
            </div>
            <div className="text-3xl font-bold">{subscribedTraders.length}</div>
            <div className="text-green-100 text-sm mt-1">Pro Traders</div>
          </div>

          <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl shadow-lg p-6 text-white">
            <div className="flex items-center justify-between mb-2">
              <span className="text-3xl">💎</span>
              <span className="text-sm opacity-80">Exclusive</span>
            </div>
            <div className="text-3xl font-bold">Premium</div>
            <div className="text-purple-100 text-sm mt-1">Member Status</div>
          </div>

          <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-xl shadow-lg p-6 text-white">
            <div className="flex items-center justify-between mb-2">
              <span className="text-3xl">🔥</span>
              <span className="text-sm opacity-80">Streak</span>
            </div>
            <div className="text-3xl font-bold">7</div>
            <div className="text-orange-100 text-sm mt-1">Days Active</div>
          </div>
        </div>

        {/* Subscribed Traders Section */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              💼 Your Exclusive Traders
            </h2>
            <Link href="/traders">
              <span className="text-blue-600 hover:text-blue-700 font-medium cursor-pointer">
                Browse All Traders →
              </span>
            </Link>
          </div>

          {subscribedTraders.length === 0 ? (
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-dashed border-blue-300 rounded-xl p-12 text-center">
              <span className="text-6xl mb-4 block">⚽</span>
              <h3 className="text-xl font-bold text-gray-900 mb-2">
                No Subscriptions Yet
              </h3>
              <p className="text-gray-600 mb-6">
                Subscribe to elite traders to unlock exclusive signals and insights
              </p>
              <Link href="/traders">
                <span className="inline-block bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-8 py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-indigo-700 transition-all shadow-lg cursor-pointer">
                  Discover Pro Traders
                </span>
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {subscribedTraders.map(trader => (
                <div key={trader.id} className="bg-white rounded-xl shadow-lg overflow-hidden hover:shadow-xl transition-shadow border-2 border-green-200">
                  <div className="bg-gradient-to-r from-green-600 to-emerald-600 p-4">
                    <div className="flex items-center">
                      <img
                        src={trader.avatar_url || '/default-avatar.png'}
                        alt={trader.username}
                        className="w-16 h-16 rounded-full border-4 border-white"
                      />
                      <div className="ml-4 text-white">
                        <h3 className="font-bold text-lg">{trader.username}</h3>
                        <span className="text-sm opacity-90">✓ Subscribed</span>
                      </div>
                    </div>
                  </div>
                  <div className="p-4">
                    <div className="grid grid-cols-2 gap-4 text-center mb-4">
                      <div>
                        <div className="text-2xl font-bold text-green-600">
                          {trader.win_rate ? Number(trader.win_rate).toFixed(0) : 0}%
                        </div>
                        <div className="text-xs text-gray-500">Win Rate</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold text-blue-600">
                          {trader.active_signals || 0}
                        </div>
                        <div className="text-xs text-gray-500">Active Signals</div>
                      </div>
                    </div>
                    <Link href={`/traders/${trader.id}`}>
                      <button className="w-full bg-green-600 text-white py-2 rounded-lg font-semibold hover:bg-green-700 transition-colors">
                        View Exclusive Content
                      </button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Signals */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              ⚡ Latest Trading Signals
            </h2>
            <Link href="/signals">
              <span className="text-blue-600 hover:text-blue-700 font-medium cursor-pointer">
                View All Signals →
              </span>
            </Link>
          </div>

          {recentSignals.length === 0 ? (
            <div className="bg-gray-50 rounded-xl p-12 text-center">
              <span className="text-5xl mb-4 block">📭</span>
              <p className="text-gray-500">No active signals at the moment</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {recentSignals.slice(0, 6).map(signal => (
                <div
                  key={signal.id}
                  onClick={() => router.push(`/signals/${signal.id}`)}
                  className="bg-white rounded-xl shadow-lg hover:shadow-xl transition-all cursor-pointer border-l-4 border-green-500 overflow-hidden"
                >
                  <div className="p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center space-x-4">
                        <img
                          src={signal.player_image || '/default-player.png'}
                          alt={signal.player_name}
                          className="w-20 h-20 object-contain bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg p-2"
                        />
                        <div>
                          <h3 className="font-bold text-lg text-gray-900">{signal.player_name}</h3>
                          <p className="text-sm text-gray-500">
                            by <span className="text-blue-600 font-medium">{signal.trader_username}</span>
                          </p>
                        </div>
                      </div>
                      <div className={`px-4 py-2 rounded-full text-sm font-bold ${
                        signal.status === 'active' ? 'bg-green-100 text-green-700' :
                        signal.status === 'closed' ? 'bg-gray-100 text-gray-700' :
                        'bg-yellow-100 text-yellow-700'
                      }`}>
                        {signal.status?.toUpperCase()}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div className="bg-blue-50 rounded-lg p-3">
                        <div className="text-xs text-gray-600 mb-1">Buy Price</div>
                        <div className="font-bold text-blue-600">
                          {signal.entry_price_min}{signal.entry_price_max ? `-${signal.entry_price_max}` : ''}
                        </div>
                      </div>
                      {signal.sell_price && (
                        <div className="bg-green-50 rounded-lg p-3">
                          <div className="text-xs text-gray-600 mb-1">Target Price</div>
                          <div className="font-bold text-green-600">{signal.sell_price}</div>
                        </div>
                      )}
                    </div>

                    {signal.roi !== null && (
                      <div className={`text-center py-2 rounded-lg font-bold ${
                        Number(signal.roi) > 0 ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                      }`}>
                        {Number(signal.roi) > 0 ? '📈' : '📉'} {Number(signal.roi) > 0 ? '+' : ''}{Number(signal.roi).toFixed(1)}% ROI
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
