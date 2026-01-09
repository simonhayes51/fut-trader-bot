import { useState, useEffect } from 'react';
import Link from 'next/link';
import Layout from '../components/layout/Layout';
import { api } from '../lib/api';
import StarRating from '../components/reviews/StarRating';

export default function Home() {
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
        api.getSignals({ sort: 'recent', limit: 5, status: 'all' })
      ]);

      setTopTraders(tradersRes.data.traders);
      setRecentSignals(signalsRes.data.signals);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="FUT Hub - Premium FUT Trading Platform">
      {/* Hero Section */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center">
            <h1 className="text-5xl font-bold mb-6">
              Welcome to FUT Hub
            </h1>
            <p className="text-xl mb-8 text-blue-100">
              Connect with top FUT traders, get premium signals, and maximize your coin profits
            </p>
            <div className="flex justify-center space-x-4">
              <Link href="/traders" className="bg-white text-blue-600 px-8 py-3 rounded-lg font-semibold hover:bg-gray-100 transition-colors">
                Browse Traders
              </Link>
              <Link href="/signup" className="bg-blue-500 text-white px-8 py-3 rounded-lg font-semibold hover:bg-blue-400 transition-colors">
                Sign Up Free
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="bg-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center mb-12">Why Choose FUT Hub?</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center p-6">
              <div className="text-4xl mb-4">📈</div>
              <h3 className="text-xl font-semibold mb-2">Premium Traders</h3>
              <p className="text-gray-600">
                Subscribe to verified traders with proven track records and consistent profits
              </p>
            </div>
            <div className="text-center p-6">
              <div className="text-4xl mb-4">⚡</div>
              <h3 className="text-xl font-semibold mb-2">Real-Time Signals</h3>
              <p className="text-gray-600">
                Get instant notifications when traders post new buy/sell signals
              </p>
            </div>
            <div className="text-center p-6">
              <div className="text-4xl mb-4">🎯</div>
              <h3 className="text-xl font-semibold mb-2">Free Tools</h3>
              <p className="text-gray-600">
                Access price checkers, SBC solutions, and community guides for free
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Top Traders Section */}
      <div className="bg-gray-50 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center mb-8">
            <h2 className="text-3xl font-bold">Top Traders</h2>
            <Link href="/traders" className="text-blue-600 hover:text-blue-700 font-medium">
              View All →
            </Link>
          </div>

          {loading ? (
            <div className="text-center py-12">Loading...</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {topTraders.map(trader => (
                <Link key={trader.id} href={`/traders/${trader.id}`}>
                  <div className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow p-6 cursor-pointer">
                    <div className="flex items-center mb-4">
                      <img
                        src={trader.avatar_url || '/default-avatar.png'}
                        alt={trader.username}
                        className="w-12 h-12 rounded-full mr-3"
                      />
                      <div>
                        <h3 className="font-semibold">{trader.username}</h3>
                        <div className="flex items-center">
                          <StarRating rating={trader.avg_rating || 0} size="sm" />
                          <span className="text-sm text-gray-500 ml-2">
                            ({trader.review_count || 0})
                          </span>
                        </div>
                      </div>
                    </div>

                    <p className="text-gray-600 text-sm mb-4 line-clamp-2">
                      {trader.bio || 'Expert FUT trader'}
                    </p>

                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div>
                        <div className="text-2xl font-bold text-green-600">
                          {trader.win_rate?.toFixed(0) || 0}%
                        </div>
                        <div className="text-xs text-gray-500">Win Rate</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold text-blue-600">
                          {trader.total_signals || 0}
                        </div>
                        <div className="text-xs text-gray-500">Signals</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold text-purple-600">
                          {trader.total_subscribers || 0}
                        </div>
                        <div className="text-xs text-gray-500">Subs</div>
                      </div>
                    </div>

                    {trader.subscription_price && (
                      <div className="mt-4 pt-4 border-t border-gray-200 text-center">
                        <span className="text-lg font-bold text-gray-900">
                          £{trader.subscription_price}/month
                        </span>
                      </div>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Signals Section */}
      <div className="bg-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center mb-8">
            <h2 className="text-3xl font-bold">Recent Signals</h2>
            <Link href="/signals" className="text-blue-600 hover:text-blue-700 font-medium">
              View All →
            </Link>
          </div>

          {loading ? (
            <div className="text-center py-12">Loading...</div>
          ) : (
            <div className="space-y-4">
              {recentSignals.map(signal => (
                <Link key={signal.id} href={`/signals/${signal.id}`}>
                  <div className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <img
                          src={signal.player_image || '/default-player.png'}
                          alt={signal.player_name}
                          className="w-16 h-16 object-contain"
                        />
                        <div>
                          <h3 className="font-semibold">{signal.player_name}</h3>
                          <p className="text-sm text-gray-500">by {signal.trader_username}</p>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                          signal.status === 'active' ? 'bg-green-100 text-green-800' :
                          signal.status === 'closed' ? 'bg-gray-100 text-gray-800' :
                          'bg-yellow-100 text-yellow-800'
                        }`}>
                          {signal.status}
                        </div>
                        {signal.roi && (
                          <div className={`text-lg font-bold mt-1 ${
                            signal.roi > 0 ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {signal.roi > 0 ? '+' : ''}{signal.roi.toFixed(1)}% ROI
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* CTA Section */}
      <div className="bg-blue-600 text-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to Start Trading?</h2>
          <p className="text-xl mb-8 text-blue-100">
            Join thousands of traders making coins with FUT Hub
          </p>
          <Link href="/signup" className="bg-white text-blue-600 px-8 py-3 rounded-lg font-semibold hover:bg-gray-100 transition-colors inline-block">
            Get Started Free
          </Link>
        </div>
      </div>
    </Layout>
  );
}
