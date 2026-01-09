import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/layout/Layout';
import { api } from '../../lib/api';
import CommentThread from '../../components/comments/CommentThread';
import toast from 'react-hot-toast';

export default function SignalDetailPage() {
  const router = useRouter();
  const { id } = router.query;

  const [signal, setSignal] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      fetchSignal();
    }
  }, [id]);

  const fetchSignal = async () => {
    try {
      setLoading(true);
      const response = await api.getSignal(id);
      setSignal(response.data.signal);
    } catch (error) {
      console.error('Failed to fetch signal:', error);
      toast.error('Failed to load signal');
    } finally {
      setLoading(false);
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

  if (!signal) {
    return (
      <Layout title="Signal Not Found">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Signal Not Found</h1>
            <button onClick={() => router.push('/signals')} className="btn-primary">
              Browse Signals
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title={`${signal.player_name} Signal - FUT Hub`}>
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Signal Card */}
        <div className="bg-white rounded-lg shadow-lg p-8 mb-8">
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center space-x-6">
              <img
                src={signal.player_image || '/default-player.png'}
                alt={signal.player_name}
                className="w-32 h-32 object-contain"
              />
              <div>
                <h1 className="text-3xl font-bold mb-2">{signal.player_name}</h1>
                <p className="text-gray-600 mb-2">
                  Posted by{' '}
                  <span
                    onClick={() => router.push(`/traders/${signal.trader_id}`)}
                    className="text-blue-600 hover:underline cursor-pointer font-medium"
                  >
                    {signal.trader_username}
                  </span>
                </p>
                <p className="text-sm text-gray-500">
                  {new Date(signal.created_at).toLocaleString()}
                </p>
              </div>
            </div>

            <div className={`px-6 py-3 rounded-full text-lg font-medium ${
              signal.status === 'active' ? 'bg-green-100 text-green-800' :
              signal.status === 'closed' ? 'bg-gray-100 text-gray-800' :
              'bg-yellow-100 text-yellow-800'
            }`}>
              {signal.status.toUpperCase()}
            </div>
          </div>

          {/* Price Information */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div className="bg-blue-50 rounded-lg p-4">
              <div className="text-sm text-gray-600 mb-1">Entry Price</div>
              <div className="text-2xl font-bold text-blue-600">
                {signal.entry_price_min}
                {signal.entry_price_max && ` - ${signal.entry_price_max}`}
              </div>
            </div>

            {signal.sell_price && (
              <div className="bg-green-50 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">Target Sell Price</div>
                <div className="text-2xl font-bold text-green-600">
                  {signal.sell_price}
                </div>
              </div>
            )}

            {signal.exit_price && (
              <div className="bg-purple-50 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">Exit Price</div>
                <div className="text-2xl font-bold text-purple-600">
                  {signal.exit_price}
                </div>
              </div>
            )}
          </div>

          {/* ROI */}
          {signal.roi !== null && (
            <div className="mb-6">
              <div className={`inline-block px-8 py-4 rounded-lg ${
                signal.roi > 0 ? 'bg-green-100' : 'bg-red-100'
              }`}>
                <div className="text-sm text-gray-600 mb-1">Return on Investment</div>
                <div className={`text-4xl font-bold ${
                  signal.roi > 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {signal.roi > 0 ? '+' : ''}{signal.roi.toFixed(1)}%
                </div>
              </div>
            </div>
          )}

          {/* Notes */}
          {signal.notes && (
            <div className="bg-gray-50 rounded-lg p-4 mb-6">
              <h3 className="font-semibold mb-2">Trader Notes</h3>
              <p className="text-gray-700 whitespace-pre-wrap">{signal.notes}</p>
            </div>
          )}

          {/* Meta Info */}
          <div className="flex items-center justify-between pt-6 border-t border-gray-200 text-sm text-gray-500">
            <span>{signal.view_count || 0} views</span>
            <span>{signal.comment_count || 0} comments</span>
          </div>
        </div>

        {/* Comments Section */}
        <CommentThread
          commentableType="signal"
          commentableId={id}
          allowReplies={true}
          showVotes={true}
        />
      </div>
    </Layout>
  );
}
