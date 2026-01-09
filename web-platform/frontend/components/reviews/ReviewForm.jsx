import { useState } from 'react';
import axios from 'axios';
import StarRating from './StarRating';

export default function ReviewForm({ reviewableType, reviewableId, onSuccess }) {
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState('');
  const [reviewText, setReviewText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (rating === 0) {
      setError('Please select a rating');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await axios.post('/api/reviews', {
        reviewableType,
        reviewableId,
        rating,
        title,
        reviewText
      });

      // Reset form
      setRating(5);
      setTitle('');
      setReviewText('');

      // Call success callback
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to submit review');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
      <h3 className="text-lg font-semibold">Write a Review</h3>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Rating */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Your Rating *
        </label>
        <div className="flex items-center space-x-1">
          {[1, 2, 3, 4, 5].map(star => (
            <button
              key={star}
              type="button"
              onClick={() => setRating(star)}
              className="text-3xl focus:outline-none"
            >
              {star <= rating ? '⭐' : '☆'}
            </button>
          ))}
          <span className="ml-2 text-gray-600">
            {rating}/5 stars
          </span>
        </div>
      </div>

      {/* Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Review Title (optional)
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Summarize your experience..."
          maxLength={255}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Review Text */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Your Review (optional)
        </label>
        <textarea
          value={reviewText}
          onChange={(e) => setReviewText(e.target.value)}
          placeholder="Share your thoughts..."
          rows={5}
          maxLength={2000}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <p className="text-sm text-gray-500 mt-1">
          {reviewText.length}/2000 characters
        </p>
      </div>

      {/* Submit Button */}
      <div className="flex justify-end space-x-3">
        <button
          type="submit"
          disabled={submitting || rating === 0}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? 'Submitting...' : 'Submit Review'}
        </button>
      </div>
    </form>
  );
}
