import { useState } from 'react';
import axios from 'axios';
import StarRating from './StarRating';
import ReviewForm from './ReviewForm';

export default function ReviewList({ reviewableType, reviewableId, allowPosting = false }) {
  const [reviews, setReviews] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState('helpful');
  const [showForm, setShowForm] = useState(false);

  // Fetch reviews
  const fetchReviews = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `/api/reviews/${reviewableType}/${reviewableId}?sort=${sort}`
      );
      setReviews(response.data.reviews);
      setStats(response.data.stats);
    } catch (error) {
      console.error('Failed to fetch reviews:', error);
    } finally {
      setLoading(false);
    }
  };

  // Vote on review (helpful/unhelpful)
  const handleVote = async (reviewId, voteType) => {
    try {
      await axios.post(`/api/reviews/${reviewId}/vote`, { voteType });
      fetchReviews(); // Refresh
    } catch (error) {
      console.error('Failed to vote:', error);
    }
  };

  // Use effect to fetch on mount
  useState(() => {
    fetchReviews();
  }, [reviewableType, reviewableId, sort]);

  if (loading) {
    return <div className="animate-pulse">Loading reviews...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      {stats && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-4xl font-bold">{stats.avg_rating}</span>
                <StarRating rating={stats.avg_rating} size="lg" />
              </div>
              <p className="text-gray-600 mt-1">{stats.total_reviews} reviews</p>
            </div>

            {/* Rating Distribution */}
            <div className="space-y-1">
              {[5, 4, 3, 2, 1].map(star => {
                const count = parseInt(stats[`${['five', 'four', 'three', 'two', 'one'][5 - star]}_star`] || 0);
                const percentage = stats.total_reviews > 0
                  ? (count / stats.total_reviews * 100).toFixed(0)
                  : 0;

                return (
                  <div key={star} className="flex items-center space-x-2 text-sm">
                    <span className="w-12">{star} star</span>
                    <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-yellow-400"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                    <span className="w-12 text-gray-600">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Write Review Button */}
          {allowPosting && (
            <button
              onClick={() => setShowForm(!showForm)}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              {showForm ? 'Cancel' : 'Write a Review'}
            </button>
          )}
        </div>
      )}

      {/* Review Form */}
      {showForm && (
        <ReviewForm
          reviewableType={reviewableType}
          reviewableId={reviewableId}
          onSuccess={() => {
            setShowForm(false);
            fetchReviews();
          }}
        />
      )}

      {/* Sort Options */}
      <div className="flex space-x-4 border-b border-gray-200 pb-2">
        {['helpful', 'recent', 'rating_high', 'rating_low'].map(option => (
          <button
            key={option}
            onClick={() => setSort(option)}
            className={`px-3 py-1 rounded ${
              sort === option
                ? 'bg-blue-600 text-white'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {option === 'helpful' && 'Most Helpful'}
            {option === 'recent' && 'Most Recent'}
            {option === 'rating_high' && 'Highest Rating'}
            {option === 'rating_low' && 'Lowest Rating'}
          </button>
        ))}
      </div>

      {/* Reviews List */}
      <div className="space-y-4">
        {reviews.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No reviews yet. Be the first!</p>
        ) : (
          reviews.map(review => (
            <ReviewCard
              key={review.id}
              review={review}
              onVote={handleVote}
            />
          ))
        )}
      </div>
    </div>
  );
}

// Individual Review Card Component
function ReviewCard({ review, onVote }) {
  const [voting, setVoting] = useState(false);

  const handleVoteClick = async (voteType) => {
    if (voting) return;
    setVoting(true);
    await onVote(review.id, voteType);
    setVoting(false);
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          <img
            src={review.avatar_url || '/default-avatar.png'}
            alt={review.username}
            className="w-10 h-10 rounded-full"
          />
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-semibold">{review.username}</span>
              {review.is_verified_trader && (
                <span className="text-blue-600">✓</span>
              )}
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-500">
              <StarRating rating={review.rating} size="sm" />
              <span>•</span>
              <span>{new Date(review.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Title */}
      {review.title && (
        <h4 className="font-semibold text-lg mb-2">{review.title}</h4>
      )}

      {/* Review Text */}
      {review.review_text && (
        <p className="text-gray-700 mb-4">{review.review_text}</p>
      )}

      {/* Helpful Votes */}
      <div className="flex items-center space-x-4 pt-3 border-t border-gray-200">
        <span className="text-sm text-gray-600">Was this helpful?</span>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => handleVoteClick('helpful')}
            disabled={voting}
            className={`px-3 py-1 rounded text-sm ${
              review.user_vote === 'helpful'
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 hover:bg-gray-200'
            }`}
          >
            👍 Helpful ({review.helpful_count})
          </button>
          <button
            onClick={() => handleVoteClick('unhelpful')}
            disabled={voting}
            className={`px-3 py-1 rounded text-sm ${
              review.user_vote === 'unhelpful'
                ? 'bg-red-100 text-red-700'
                : 'bg-gray-100 hover:bg-gray-200'
            }`}
          >
            👎 Not helpful ({review.unhelpful_count})
          </button>
        </div>
      </div>
    </div>
  );
}
