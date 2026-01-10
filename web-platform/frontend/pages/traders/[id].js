import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/layout/Layout';
import { api } from '../../lib/api';
import toast from 'react-hot-toast';

export default function TraderProfilePage() {
  const router = useRouter();
  const { id } = router.query;

  const [trader, setTrader] = useState(null);
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState(false);

  useEffect(() => {
    if (id) {
      fetchTraderData();
    }
  }, [id]);

  const fetchTraderData = async () => {
    try {
      setLoading(true);
      const traderRes = await api.getTrader(id);

      setTrader(traderRes.data.trader);
      setSignals(traderRes.data.recent_signals || []);
      setStats(traderRes.data.stats);
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
        <div className="min-h-screen bg-black flex items-center justify-center">
          <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-cyan-500"></div>
        </div>
      </Layout>
    );
  }

  if (!trader) {
    return (
      <Layout title="Trader Not Found">
        <div className="min-h-screen bg-black flex items-center justify-center">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-white mb-4">Trader Not Found</h1>
            <button
              onClick={() => router.push('/traders')}
              className="px-8 py-3 bg-cyan-500 text-white rounded-xl font-bold hover:bg-cyan-600"
            >
              Browse Traders
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title={`${trader.username} - FUT Hub`}>
      <div className="min-h-screen bg-black">
        {/* Simple trader profile - will be redesigned */}
        <div className="max-w-7xl mx-auto px-4 py-12">
          <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-gray-800 p-8">
            <div className="flex items-center gap-6 mb-8">
              <img
                src={trader.avatar_url || 'https://cdn.discordapp.com/embed/avatars/0.png'}
                alt={trader.username}
                className="w-32 h-32 rounded-full border-4 border-cyan-500"
              />
              <div className="flex-1">
                <h1 className="text-4xl font-black text-white mb-2">{trader.username}</h1>
                <p className="text-gray-400 mb-4">{trader.bio}</p>
                <div className="flex gap-6 text-sm">
                  <div>
                    <span className="text-gray-400">Win Rate:</span>
                    <span className="ml-2 font-bold text-white">
                      {trader.win_rate ? Number(trader.win_rate).toFixed(1) : 0}%
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Signals:</span>
                    <span className="ml-2 font-bold text-white">{trader.total_signals || 0}</span>
                  </div>
                </div>
              </div>
              <button
                onClick={handleSubscribe}
                disabled={subscribing}
                className="px-8 py-4 bg-gradient-to-r from-cyan-500 to-cyan-600 text-white rounded-xl font-bold hover:from-cyan-600 hover:to-cyan-700 transition-all"
              >
                {subscribing ? 'Loading...' : trader.is_subscribed ? 'Unsubscribe' : 'Subscribe'}
              </button>
            </div>

            <div className="space-y-4">
              {signals.length === 0 ? (
                <p className="text-gray-400 text-center py-8">No signals yet</p>
              ) : (
                signals.map(signal => (
                  <div
                    key={signal.id}
                    onClick={() => router.push(`/signals/${signal.id}`)}
                    className="bg-gray-900/50 border border-gray-800 rounded-xl p-6 cursor-pointer hover:border-gray-700 transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-xl font-bold text-white mb-2">
                          {signal.player_name || signal.card_name}
                        </h3>
                        <div className="flex gap-4 text-sm">
                          <span className="text-gray-400">
                            Buy: <span className="text-white font-bold">{signal.entry_price_min}</span>
                          </span>
                          {signal.sell_price && (
                            <span className="text-gray-400">
                              Sell: <span className="text-white font-bold">{signal.sell_price}</span>
                            </span>
                          )}
                        </div>
                      </div>
                      {signal.roi !== null && (
                        <div className={`text-2xl font-black ${
                          Number(signal.roi) > 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {Number(signal.roi) > 0 ? '+' : ''}{Number(signal.roi).toFixed(1)}%
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
