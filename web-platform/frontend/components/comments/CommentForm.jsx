import { useState } from 'react';
import axios from 'axios';

export default function CommentForm({
  commentableType,
  commentableId,
  parentCommentId = null,
  onSuccess,
  onCancel
}) {
  const [commentText, setCommentText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const isReply = parentCommentId !== null;

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!commentText.trim()) {
      setError('Comment cannot be empty');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await axios.post('/api/comments', {
        commentableType,
        commentableId,
        commentText: commentText.trim(),
        parentCommentId
      });

      // Reset form
      setCommentText('');

      // Call success callback
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to post comment');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
          {error}
        </div>
      )}

      <textarea
        value={commentText}
        onChange={(e) => setCommentText(e.target.value)}
        placeholder={isReply ? 'Write a reply...' : 'Write a comment...'}
        rows={isReply ? 3 : 4}
        maxLength={2000}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
      />

      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {commentText.length}/2000 characters
        </p>

        <div className="flex space-x-2">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={submitting || !commentText.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Posting...' : isReply ? 'Reply' : 'Comment'}
          </button>
        </div>
      </div>
    </form>
  );
}
