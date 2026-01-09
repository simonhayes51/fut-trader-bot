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
      <div className="relative bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 text-white overflow-hidden">
        <div className="absolute inset-0 bg-black opacity-10"></div>
        <div className="absolute inset-0" style={{
          backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.1) 1px, transparent 0)',
          backgroundSize: '40px 40px'
        }}></div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 md:py-32">
          <div className="text-center">
            <div className="inline-block mb-4">
              <span className="px-4 py-2 bg-blue-500/30 backdrop-blur-sm rounded-full text-sm font-semibold border border-blue-400/30">
                ⚡ #1 FUT Trading Platform
              </span>
            </div>
            <h1 className="text-5xl md:text-7xl font-extrabold mb-6 leading-tight">
              Trade Smarter,<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-200 to-cyan-200">
                Win Bigger
              </span>
            </h1>
            <p className="text-xl md:text-2xl mb-10 text-blue-100 max-w-3xl mx-auto font-light">
              Connect with elite FUT traders, access premium signals, and maximize your coin profits with data-driven insights
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <Link href="/traders" className="group px-8 py-4 bg-white text-blue-600 rounded-xl font-bold text-lg hover:bg-blue-50 transition-all shadow-xl hover:shadow-2xl hover:scale-105 transform">
                Explore Traders
                <span className="inline-block ml-2 group-hover:translate-x-1 transition-transform">→</span>
              </Link>
              <Link href="/signup" className="px-8 py-4 bg-blue-500/20 backdrop-blur-sm text-white rounded-xl font-bold text-lg hover:bg-blue-500/30 transition-all border-2 border-white/20">
                Start Free Trial
              </Link>
            </div>

            {/* Stats */}
            <div className="mt-16 grid grid-cols-3 gap-8 max-w-3xl mx-auto">
              <div className="text-center">
                <div className="text-4xl md:text-5xl font-bold mb-2">2.5K+</div>
                <div className="text-blue-200 text-sm md:text-base">Active Traders</div>
              </div>
              <div className="text-center border-x border-white/20">
                <div className="text-4xl md:text-5xl font-bold mb-2">85%</div>
                <div className="text-blue-200 text-sm md:text-base">Avg Win Rate</div>
              </div>
              <div className="text-center">
                <div className="text-4xl md:text-5xl font-bold mb-2">10M+</div>
                <div className="text-blue-200 text-sm md:text-base">Coins Earned</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="bg-gray-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">Why Choose FUT Hub?</h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">Everything you need to dominate the FUT market</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all hover:-translate-y-2 border border-gray-100">
              <div className="w-16 h-16 bg-gradient-to-br from-green-400 to-green-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold mb-3 text-gray-900">Verified Traders</h3>
              <p className="text-gray-600 leading-relaxed">
                Subscribe to verified traders with proven track records and consistent 70-90% win rates
              </p>
            </div>

            <div className="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all hover:-translate-y-2 border border-gray-100">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-400 to-blue-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold mb-3 text-gray-900">Real-Time Signals</h3>
              <p className="text-gray-600 leading-relaxed">
                Get instant notifications when traders post buy/sell signals with detailed entry and exit strategies
              </p>
            </div>

            <div className="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all hover:-translate-y-2 border border-gray-100">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-400 to-purple-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold mb-3 text-gray-900">Free Tools</h3>
              <p className="text-gray-600 leading-relaxed">
                Access price checkers, SBC solutions, and market analysis tools completely free
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Top Traders Section */}
      <div className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center mb-12">
            <div>
              <h2 className="text-4xl font-bold text-gray-900 mb-2">Top Rated Traders</h2>
              <p className="text-gray-600">Learn from the best in the business</p>
            </div>
            <Link href="/traders" className="hidden md:block text-blue-600 hover:text-blue-700 font-semibold text-lg group">
              View All
              <span className="inline-block ml-1 group-hover:translate-x-1 transition-transform">→</span>
            </Link>
          </div>

          {loading ? (
            <div className="text-center py-20">
              <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {topTraders.map(trader => (
                <Link key={trader.id} href={`/traders/${trader.id}`}>
                  <div className="group bg-gradient-to-br from-white to-gray-50 rounded-2xl shadow-lg hover:shadow-2xl transition-all p-6 cursor-pointer border border-gray-100 hover:border-blue-200 hover:-translate-y-1">
                    <div className="flex items-start mb-4">
                      <img
                        src={trader.avatar_url || '/default-avatar.png'}
                        alt={trader.username}
                        className="w-16 h-16 rounded-full mr-4 ring-4 ring-blue-50 group-hover:ring-blue-100 transition-all"
                      />
                      <div className="flex-1">
                        <div className="flex items-center mb-1">
                          <h3 className="font-bold text-lg text-gray-900">{trader.username}</h3>
                          {trader.is_verified_trader && (
                            <svg className="w-5 h-5 text-blue-500 ml-2" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                          )}
                        </div>
                        <div className="flex items-center">
                          <StarRating rating={trader.avg_rating || 0} size="sm" />
                          <span className="text-sm text-gray-500 ml-2">
                            ({trader.review_count || 0})
                          </span>
                        </div>
                      </div>
                    </div>

                    <p className="text-gray-600 text-sm mb-4 line-clamp-2 leading-relaxed">
                      {trader.bio || 'Expert FUT trader with proven results'}
                    </p>

                    <div className="grid grid-cols-3 gap-3 mb-4">
                      <div className="bg-green-50 rounded-xl p-3 text-center">
                        <div className="text-xl font-bold text-green-600">
                          {trader.win_rate ? Number(trader.win_rate).toFixed(0) : 0}%
                        </div>
                        <div className="text-xs text-gray-600 mt-1">Win Rate</div>
                      </div>
                      <div className="bg-blue-50 rounded-xl p-3 text-center">
                        <div className="text-xl font-bold text-blue-600">
                          {trader.total_signals || 0}
                        </div>
                        <div className="text-xs text-gray-600 mt-1">Signals</div>
                      </div>
                      <div className="bg-purple-50 rounded-xl p-3 text-center">
                        <div className="text-xl font-bold text-purple-600">
                          {trader.total_subscribers || 0}
                        </div>
                        <div className="text-xs text-gray-600 mt-1">Subs</div>
                      </div>
                    </div>

                    {trader.subscription_price && (
                      <div className="pt-4 border-t border-gray-200 flex items-center justify-between">
                        <span className="text-2xl font-bold text-gray-900">
                          £{trader.subscription_price}<span className="text-sm text-gray-500">/mo</span>
                        </span>
                        <span className="text-blue-600 font-semibold group-hover:translate-x-1 transition-transform inline-block">
                          View →
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
      <div className="bg-gradient-to-br from-gray-50 to-gray-100 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center mb-12">
            <div>
              <h2 className="text-4xl font-bold text-gray-900 mb-2">Latest Signals</h2>
              <p className="text-gray-600">Hot picks from our top traders</p>
            </div>
            <Link href="/signals" className="hidden md:block text-blue-600 hover:text-blue-700 font-semibold text-lg group">
              View All
              <span className="inline-block ml-1 group-hover:translate-x-1 transition-transform">→</span>
            </Link>
          </div>

          {loading ? (
            <div className="text-center py-20">
              <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <div className="space-y-4">
              {recentSignals.map(signal => (
                <Link key={signal.id} href={`/signals/${signal.id}`}>
                  <div className="bg-white rounded-2xl shadow-md hover:shadow-xl transition-all p-6 cursor-pointer group border border-gray-100 hover:border-blue-200">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-6 flex-1">
                        <div className="w-20 h-20 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl flex items-center justify-center">
                          <span className="text-3xl">⚽</span>
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center mb-1">
                            <h3 className="font-bold text-xl text-gray-900">{signal.player_name}</h3>
                            <span className={`ml-3 px-3 py-1 rounded-full text-xs font-bold ${
                              signal.status === 'active' ? 'bg-green-100 text-green-700' :
                              signal.status === 'closed' ? 'bg-gray-100 text-gray-700' :
                              'bg-yellow-100 text-yellow-700'
                            }`}>
                              {signal.status.toUpperCase()}
                            </span>
                          </div>
                          <p className="text-sm text-gray-500">
                            by <span className="text-blue-600 font-medium">{signal.trader_username}</span>
                            <span className="mx-2">•</span>
                            {new Date(signal.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>

                      <div className="text-right">
                        {signal.roi != null && (
                          <div className={`text-3xl font-bold mb-1 ${
                            Number(signal.roi) > 0 ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {Number(signal.roi) > 0 ? '+' : ''}{Number(signal.roi).toFixed(1)}%
                          </div>
                        )}
                        <div className="text-sm text-gray-500">
                          {signal.view_count || 0} views
                        </div>
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
      <div className="relative bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-20 overflow-hidden">
        <div className="absolute inset-0 bg-black opacity-10"></div>
        <div className="absolute inset-0" style={{
          backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.1) 1px, transparent 0)',
          backgroundSize: '40px 40px'
        }}></div>

        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl md:text-5xl font-bold mb-6">Ready to Level Up Your Trading?</h2>
          <p className="text-xl mb-10 text-blue-100">
            Join thousands of traders already profiting with FUT Hub
          </p>
          <Link href="/signup" className="inline-block bg-white text-blue-600 px-10 py-4 rounded-xl font-bold text-lg hover:bg-blue-50 transition-all shadow-2xl hover:scale-105 transform">
            Get Started - It's Free
          </Link>
          <p className="mt-6 text-blue-200 text-sm">No credit card required • Cancel anytime</p>
        </div>
      </div>
    </Layout>
  );
}
