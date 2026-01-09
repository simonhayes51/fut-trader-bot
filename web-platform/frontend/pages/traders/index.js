import { useState, useEffect } from 'react';
import Link from 'next/link';
import Layout from '../../components/layout/Layout';
import { api } from '../../lib/api';
import StarRating from '../../components/reviews/StarRating';

export default function TradersPage() {
  const [traders, setTraders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState('top');
  const [priceFilter, setPriceFilter] = useState('all');

  useEffect(() => {
    fetchTraders();
  }, [sort, priceFilter]);

  const fetchTraders = async () => {
    try {
      setLoading(true);
      const params = { sort };

      if (priceFilter === 'free') {
        params.free = true;
      } else if (priceFilter !== 'all') {
        params.maxPrice = priceFilter;
      }

      const response = await api.getTraders(params);
      setTraders(response.data.traders);
    } catch (error) {
      console.error('Failed to fetch traders:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="Browse Traders - FUT Hub">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <h1 className="text-4xl font-bold mb-8">Browse Traders</h1>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                <option value="top">Top Rated</option>
                <option value="popular">Most Popular</option>
                <option value="recent">Recently Joined</option>
                <option value="winrate">Highest Win Rate</option>
              </select>
            </div>

            {/* Price Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Price Range
              </label>
              <select
                value={priceFilter}
                onChange={(e) => setPriceFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="all">All Prices</option>
                <option value="free">Free Only</option>
                <option value="5">Under £5</option>
                <option value="10">Under £10</option>
                <option value="20">Under £20</option>
              </select>
            </div>
          </div>
        </div>

        {/* Traders Grid */}
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
          </div>
        ) : traders.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg shadow">
            <p className="text-gray-500">No traders found matching your criteria.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {traders.map(trader => (
              <Link key={trader.id} href={`/traders/${trader.id}`}>
                <div className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow p-6 cursor-pointer h-full">
                  <div className="flex items-center mb-4">
                    <img
                      src={trader.avatar_url || '/default-avatar.png'}
                      alt={trader.username}
                      className="w-16 h-16 rounded-full mr-4"
                    />
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg">{trader.username}</h3>
                      {trader.is_verified_trader && (
                        <span className="text-blue-600 text-sm">✓ Verified</span>
                      )}
                      <div className="flex items-center mt-1">
                        <StarRating rating={trader.avg_rating || 0} size="sm" />
                        <span className="text-sm text-gray-500 ml-2">
                          ({trader.review_count || 0})
                        </span>
                      </div>
                    </div>
                  </div>

                  <p className="text-gray-600 text-sm mb-4 line-clamp-3">
                    {trader.bio || 'Expert FUT trader with proven results'}
                  </p>

                  <div className="grid grid-cols-3 gap-4 text-center mb-4">
                    <div>
                      <div className="text-xl font-bold text-green-600">
                        {trader.win_rate?.toFixed(0) || 0}%
                      </div>
                      <div className="text-xs text-gray-500">Win Rate</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-blue-600">
                        {trader.total_signals || 0}
                      </div>
                      <div className="text-xs text-gray-500">Signals</div>
                    </div>
                    <div>
                      <div className="text-xl font-bold text-purple-600">
                        {trader.total_subscribers || 0}
                      </div>
                      <div className="text-xs text-gray-500">Subs</div>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-gray-200">
                    {trader.subscription_price ? (
                      <div className="flex items-center justify-between">
                        <span className="text-lg font-bold text-gray-900">
                          £{trader.subscription_price}/month
                        </span>
                        <button className="btn-primary text-sm">
                          Subscribe
                        </button>
                      </div>
                    ) : (
                      <div className="text-center">
                        <span className="text-lg font-bold text-green-600">Free</span>
                      </div>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
