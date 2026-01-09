import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/layout/Layout';
import { api } from '../../lib/api';

export default function SignalsPage() {
  const router = useRouter();
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('all');
  const [sort, setSort] = useState('recent');

  useEffect(() => {
    fetchSignals();
  }, [status, sort]);

  const fetchSignals = async () => {
    try {
      setLoading(true);
      const params = { sort, status: status === 'all' ? undefined : status };
      const response = await api.getSignals(params);
      setSignals(response.data.signals);
    } catch (error) {
      console.error('Failed to fetch signals:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="Trading Signals - FUT Hub">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <h1 className="text-4xl font-bold mb-8">Trading Signals</h1>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Status Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Status
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="all">All Signals</option>
                <option value="active">Active</option>
                <option value="closed">Closed</option>
                <option value="pending">Pending</option>
              </select>
            </div>

            {/* Sort */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Sort By
              </label>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="recent">Most Recent</option>
                <option value="roi">Highest ROI</option>
                <option value="popular">Most Popular</option>
              </select>
            </div>
          </div>
        </div>

        {/* Signals List */}
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
          </div>
        ) : signals.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg shadow">
            <p className="text-gray-500">No signals found.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {signals.map(signal => (
              <div
                key={signal.id}
                onClick={() => router.push(`/signals/${signal.id}`)}
                className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer p-6"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-6">
                    <img
                      src={signal.player_image || '/default-player.png'}
                      alt={signal.player_name}
                      className="w-20 h-20 object-contain"
                    />
                    <div>
                      <h3 className="text-xl font-semibold mb-1">{signal.player_name}</h3>
                      <p className="text-sm text-gray-500 mb-1">
                        by <span className="text-blue-600 font-medium">{signal.trader_username}</span>
                      </p>
                      <div className="flex items-center space-x-4 text-sm">
                        <span className="text-gray-600">
                          Buy: <span className="font-medium">{signal.entry_price_min}-{signal.entry_price_max || signal.entry_price_min}</span>
                        </span>
                        {signal.sell_price && (
                          <span className="text-gray-600">
                            Sell: <span className="font-medium">{signal.sell_price}</span>
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-2">
                        Posted {new Date(signal.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className={`inline-block px-4 py-2 rounded-full text-sm font-medium mb-3 ${
                      signal.status === 'active' ? 'bg-green-100 text-green-800' :
                      signal.status === 'closed' ? 'bg-gray-100 text-gray-800' :
                      'bg-yellow-100 text-yellow-800'
                    }`}>
                      {signal.status.toUpperCase()}
                    </div>
                    {signal.roi !== null && (
                      <div className={`text-2xl font-bold ${
                        Number(signal.roi) > 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {Number(signal.roi) > 0 ? '+' : ''}{Number(signal.roi).toFixed(1)}% ROI
                      </div>
                    )}
                    <div className="text-sm text-gray-500 mt-2">
                      {signal.view_count || 0} views
                    </div>
                  </div>
                </div>

                {signal.notes && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <p className="text-gray-700">{signal.notes}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
