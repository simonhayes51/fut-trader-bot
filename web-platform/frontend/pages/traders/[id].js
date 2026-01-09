import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/layout/Layout';
import { api } from '../../lib/api';
import StarRating from '../../components/reviews/StarRating';
import ReviewList from '../../components/reviews/ReviewList';
import toast from 'react-hot-toast';

export default function TraderProfilePage() {
  const router = useRouter();
  const { id } = router.query;

  const [trader, setTrader] = useState(null);
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('signals');
  const [subscribing, setSubscribing] = useState(false);

  useEffect(() => {
    if (id) {
      fetchTraderData();
    }
  }, [id]);

  const fetchTraderData = async () => {
    try {
      setLoading(true);
      const [traderRes, signalsRes, statsRes] = await Promise.all([
        api.getTrader(id),
        api.getTraderSignals(id, { limit: 10 }),
        api.getTraderStats(id)
      ]);

      setTrader(traderRes.data.trader);
      setSignals(signalsRes.data.signals);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Failed to fetch trader data:', error);
      toast.error('Failed to load trader profile');
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async () => {
    try {
      setSubscribing(true);
      if (trader.is_subscribed) {
        await api.unsubscribe(id);
        toast.success('Unsubscribed successfully');
      } else {
        await api.subscribe(id);
        toast.success('Subscribed successfully!');
      }
      fetchTraderData();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Subscription failed');
    } finally {
      setSubscribing(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Loading...">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
          </div>
        </div>
      </Layout>
    );
  }

  if (!trader) {
    return (
      <Layout title="Trader Not Found">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Trader Not Found</h1>
            <button onClick={() => router.push('/traders')} className="btn-primary">
              Browse Traders
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title={`${trader.username} - FUT Hub`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Profile Header */}
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between">
            <div className="flex items-center mb-6 md:mb-0">
              <img
                src={trader.avatar_url || '/default-avatar.png'}
                alt={trader.username}
                className="w-24 h-24 rounded-full mr-6"
              />
              <div>
                <div className="flex items-center mb-2">
                  <h1 className="text-3xl font-bold mr-3">{trader.username}</h1>
                  {trader.is_verified_trader && (
                    <span className="text-blue-600 text-xl" title="Verified Trader">✓</span>
                  )}
                </div>
                <div className="flex items-center mb-2">
                  <StarRating rating={trader.avg_rating || 0} size="lg" showNumber />
                  <span className="text-gray-500 ml-2">({trader.review_count || 0} reviews)</span>
                </div>
                <p className="text-gray-600">{trader.bio}</p>
              </div>
            </div>

            <div className="text-center">
              {trader.subscription_price ? (
                <>
                  <div className="text-3xl font-bold text-gray-900 mb-2">
                    £{trader.subscription_price}<span className="text-base text-gray-500">/month</span>
                  </div>
                  <button
                    onClick={handleSubscribe}
                    disabled={subscribing}
                    className={`px-8 py-3 rounded-lg font-semibold transition-colors ${
                      trader.is_subscribed
                        ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        : 'bg-blue-600 text-white hover:bg-blue-700'
                    }`}
                  >
                    {subscribing ? 'Processing...' : trader.is_subscribed ? 'Unsubscribe' : 'Subscribe'}
                  </button>
                </>
              ) : (
                <div className="text-2xl font-bold text-green-600">Free Trader</div>
              )}
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl font-bold text-green-600">
              {trader.win_rate?.toFixed(1) || 0}%
            </div>
            <div className="text-gray-500 mt-2">Win Rate</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl font-bold text-blue-600">
              {trader.total_signals || 0}
            </div>
            <div className="text-gray-500 mt-2">Total Signals</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl font-bold text-purple-600">
              {trader.total_subscribers || 0}
            </div>
            <div className="text-gray-500 mt-2">Subscribers</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl font-bold text-orange-600">
              {stats?.avg_roi?.toFixed(1) || 0}%
            </div>
            <div className="text-gray-500 mt-2">Avg ROI</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-lg shadow mb-8">
          <div className="border-b border-gray-200">
            <nav className="flex space-x-8 px-6">
              <button
                onClick={() => setActiveTab('signals')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'signals'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Recent Signals
              </button>
              <button
                onClick={() => setActiveTab('reviews')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'reviews'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Reviews
              </button>
              <button
                onClick={() => setActiveTab('stats')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'stats'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Detailed Stats
              </button>
            </nav>
          </div>

          <div className="p-6">
            {/* Signals Tab */}
            {activeTab === 'signals' && (
              <div className="space-y-4">
                {signals.length === 0 ? (
                  <p className="text-center text-gray-500 py-8">No signals posted yet</p>
                ) : (
                  signals.map(signal => (
                    <div
                      key={signal.id}
                      onClick={() => router.push(`/signals/${signal.id}`)}
                      className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                          <img
                            src={signal.player_image || '/default-player.png'}
                            alt={signal.player_name}
                            className="w-16 h-16 object-contain"
                          />
                          <div>
                            <h3 className="font-semibold text-lg">{signal.player_name}</h3>
                            <p className="text-sm text-gray-500">
                              Buy: {signal.entry_price_min}-{signal.entry_price_max || signal.entry_price_min}
                              {signal.sell_price && ` | Sell: ${signal.sell_price}`}
                            </p>
                            <p className="text-xs text-gray-400 mt-1">
                              {new Date(signal.created_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>

                        <div className="text-right">
                          <div className={`inline-block px-3 py-1 rounded-full text-sm font-medium mb-2 ${
                            signal.status === 'active' ? 'bg-green-100 text-green-800' :
                            signal.status === 'closed' ? 'bg-gray-100 text-gray-800' :
                            'bg-yellow-100 text-yellow-800'
                          }`}>
                            {signal.status}
                          </div>
                          {signal.roi !== null && (
                            <div className={`text-xl font-bold ${
                              signal.roi > 0 ? 'text-green-600' : 'text-red-600'
                            }`}>
                              {signal.roi > 0 ? '+' : ''}{signal.roi.toFixed(1)}%
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Reviews Tab */}
            {activeTab === 'reviews' && (
              <ReviewList
                reviewableType="trader"
                reviewableId={id}
                allowPosting={true}
              />
            )}

            {/* Stats Tab */}
            {activeTab === 'stats' && stats && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h3 className="font-semibold mb-3">7 Day Performance</h3>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Win Rate:</span>
                        <span className="font-semibold">{stats.seven_day_win_rate?.toFixed(1) || 0}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Avg ROI:</span>
                        <span className="font-semibold">{stats.seven_day_avg_roi?.toFixed(1) || 0}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Signals:</span>
                        <span className="font-semibold">{stats.seven_day_signals || 0}</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-4">
                    <h3 className="font-semibold mb-3">30 Day Performance</h3>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Win Rate:</span>
                        <span className="font-semibold">{stats.thirty_day_win_rate?.toFixed(1) || 0}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Avg ROI:</span>
                        <span className="font-semibold">{stats.thirty_day_avg_roi?.toFixed(1) || 0}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Signals:</span>
                        <span className="font-semibold">{stats.thirty_day_signals || 0}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="font-semibold mb-3">All Time Stats</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <div className="text-gray-600 text-sm">Best Trade</div>
                      <div className="text-xl font-bold text-green-600">
                        +{stats.best_trade?.toFixed(1) || 0}%
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-600 text-sm">Worst Trade</div>
                      <div className="text-xl font-bold text-red-600">
                        {stats.worst_trade?.toFixed(1) || 0}%
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-600 text-sm">Total Wins</div>
                      <div className="text-xl font-bold">{stats.total_wins || 0}</div>
                    </div>
                    <div>
                      <div className="text-gray-600 text-sm">Total Losses</div>
                      <div className="text-xl font-bold">{stats.total_losses || 0}</div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
