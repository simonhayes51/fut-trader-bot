import { useState } from 'react';
import Layout from '../../components/layout/Layout';
import { api } from '../../lib/api';
import toast from 'react-hot-toast';

export default function ToolsPage() {
  const [playerId, setPlayerId] = useState('');
  const [priceData, setPriceData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handlePriceCheck = async (e) => {
    e.preventDefault();
    if (!playerId) {
      toast.error('Please enter a player ID');
      return;
    }

    try {
      setLoading(true);
      const response = await api.getPrice(playerId);
      setPriceData(response.data);
      toast.success('Price fetched successfully!');
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to fetch price');
      setPriceData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="Free Tools - FUT Hub">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <h1 className="text-4xl font-bold mb-8">Free Trading Tools</h1>

        {/* Tools Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Price Checker */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center mb-4">
              <span className="text-3xl mr-3">💰</span>
              <h2 className="text-2xl font-bold">Price Checker</h2>
            </div>
            <p className="text-gray-600 mb-6">
              Check current market prices for any FUT player
            </p>

            <form onSubmit={handlePriceCheck} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Player ID or Name
                </label>
                <input
                  type="text"
                  value={playerId}
                  onChange={(e) => setPlayerId(e.target.value)}
                  placeholder="e.g., 20801 (Mbappe)"
                  className="input"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full"
              >
                {loading ? 'Checking...' : 'Check Price'}
              </button>
            </form>

            {priceData && (
              <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                <h3 className="font-semibold mb-3">{priceData.player_name}</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-gray-600">Current Price</div>
                    <div className="text-xl font-bold text-blue-600">
                      {priceData.price?.toLocaleString()} coins
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600">24h Change</div>
                    <div className={`text-xl font-bold ${
                      priceData.change_24h > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {priceData.change_24h > 0 ? '+' : ''}{priceData.change_24h}%
                    </div>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  Last updated: {new Date(priceData.last_updated).toLocaleString()}
                </p>
              </div>
            )}
          </div>

          {/* Coming Soon Tools */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center mb-4">
              <span className="text-3xl mr-3">📊</span>
              <h2 className="text-2xl font-bold">Market Tracker</h2>
            </div>
            <p className="text-gray-600 mb-6">
              Track price trends for multiple players
            </p>
            <div className="bg-gray-50 rounded-lg p-8 text-center">
              <p className="text-gray-500 font-medium">Coming Soon</p>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center mb-4">
              <span className="text-3xl mr-3">🎯</span>
              <h2 className="text-2xl font-bold">SBC Calculator</h2>
            </div>
            <p className="text-gray-600 mb-6">
              Calculate the cheapest solution for SBCs
            </p>
            <div className="bg-gray-50 rounded-lg p-8 text-center">
              <p className="text-gray-500 font-medium">Coming Soon</p>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center mb-4">
              <span className="text-3xl mr-3">⚡</span>
              <h2 className="text-2xl font-bold">Profit Calculator</h2>
            </div>
            <p className="text-gray-600 mb-6">
              Calculate your profit after EA tax
            </p>
            <div className="bg-gray-50 rounded-lg p-8 text-center">
              <p className="text-gray-500 font-medium">Coming Soon</p>
            </div>
          </div>
        </div>

        {/* Info Banner */}
        <div className="mt-12 bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">
            All Tools Are Free!
          </h3>
          <p className="text-blue-700">
            FUT Hub provides essential trading tools completely free. Sign up to get personalized alerts and track your favorite players.
          </p>
        </div>
      </div>
    </Layout>
  );
}
