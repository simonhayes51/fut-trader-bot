import { useState, useEffect } from 'react';
import axios from 'axios';
import CommentCard from './CommentCard';
import CommentForm from './CommentForm';

export default function CommentThread({
  commentableType,
  commentableId,
  allowReplies = true,
  showVotes = true
}) {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState('top');

  // Fetch comments
  const fetchComments = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `/api/comments/${commentableType}/${commentableId}?sort=${sort}`
      );
      setComments(response.data.comments);
    } catch (error) {
      console.error('Failed to fetch comments:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComments();
  }, [commentableType, commentableId, sort]);

  // Vote on comment
  const handleVote = async (commentId, voteType) => {
    try {
      await axios.post(`/api/comments/${commentId}/vote`, { voteType });
      fetchComments(); // Refresh
    } catch (error) {
      console.error('Failed to vote:', error);
    }
  };

  // Remove vote
  const handleRemoveVote = async (commentId) => {
    try {
      await axios.delete(`/api/comments/${commentId}/vote`);
      fetchComments();
    } catch (error) {
      console.error('Failed to remove vote:', error);
    }
  };

  // Delete comment
  const handleDelete = async (commentId) => {
    if (!confirm('Are you sure you want to delete this comment?')) return;

    try {
      await axios.delete(`/api/comments/${commentId}`);
      fetchComments();
    } catch (error) {
      console.error('Failed to delete comment:', error);
    }
  };

  if (loading) {
    return <div className="animate-pulse">Loading comments...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Comment Form */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Add a Comment</h3>
        <CommentForm
          commentableType={commentableType}
          commentableId={commentableId}
          onSuccess={fetchComments}
        />
      </div>

      {/* Sort Options */}
      <div className="flex space-x-4">
        <button
          onClick={() => setSort('top')}
          className={`px-3 py-1 rounded ${
            sort === 'top'
              ? 'bg-blue-600 text-white'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          Top
        </button>
        <button
          onClick={() => setSort('recent')}
          className={`px-3 py-1 rounded ${
            sort === 'recent'
              ? 'bg-blue-600 text-white'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          Recent
        </button>
      </div>

      {/* Comments List */}
      <div className="space-y-4">
        {comments.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            No comments yet. Start the conversation!
          </p>
        ) : (
          comments.map(comment => (
            <CommentCard
              key={comment.id}
              comment={comment}
              commentableType={commentableType}
              commentableId={commentableId}
              onVote={handleVote}
              onRemoveVote={handleRemoveVote}
              onDelete={handleDelete}
              onReply={fetchComments}
              allowReplies={allowReplies}
              showVotes={showVotes}
            />
          ))
        )}
      </div>
    </div>
  );
}
