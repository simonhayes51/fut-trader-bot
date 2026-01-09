import { useState } from 'react';
import CommentForm from './CommentForm';

export default function CommentCard({
  comment,
  commentableType,
  commentableId,
  onVote,
  onRemoveVote,
  onDelete,
  onReply,
  allowReplies,
  showVotes,
  depth = 0
}) {
  const [showReplyForm, setShowReplyForm] = useState(false);
  const [voting, setVoting] = useState(false);

  // Vote handler
  const handleVote = async (voteType) => {
    if (voting) return;

    setVoting(true);

    // If clicking same vote, remove it
    if (comment.user_vote === voteType) {
      await onRemoveVote(comment.id);
    } else {
      await onVote(comment.id, voteType);
    }

    setVoting(false);
  };

  // Calculate net votes
  const netVotes = comment.net_votes || (comment.upvotes - comment.downvotes);

  // Max depth for nesting (prevent infinite nesting)
  const maxDepth = 5;
  const isMaxDepth = depth >= maxDepth;

  return (
    <div className={`${depth > 0 ? 'ml-8 mt-4' : ''}`}>
      <div className="bg-white rounded-lg shadow p-4">
        {/* Comment Header */}
        <div className="flex items-start space-x-3">
          {/* Avatar */}
          <img
            src={comment.avatar_url || '/default-avatar.png'}
            alt={comment.username}
            className="w-8 h-8 rounded-full flex-shrink-0"
          />

          <div className="flex-1 min-w-0">
            {/* Username & Meta */}
            <div className="flex items-center space-x-2 text-sm">
              <span className="font-semibold">{comment.username}</span>
              {comment.is_verified_trader && (
                <span className="text-blue-600" title="Verified Trader">✓</span>
              )}
              {comment.is_pinned && (
                <span className="bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded text-xs">
                  Pinned
                </span>
              )}
              <span className="text-gray-500">•</span>
              <span className="text-gray-500">
                {formatTimeAgo(comment.created_at)}
              </span>
              {comment.is_edited && (
                <span className="text-gray-400 text-xs">(edited)</span>
              )}
            </div>

            {/* Comment Text */}
            <p className="mt-2 text-gray-800 whitespace-pre-wrap">
              {comment.is_deleted ? (
                <span className="text-gray-400 italic">[deleted]</span>
              ) : (
                comment.comment_text
              )}
            </p>

            {/* Action Buttons */}
            {!comment.is_deleted && (
              <div className="flex items-center space-x-4 mt-3">
                {/* Votes */}
                {showVotes && (
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleVote('upvote')}
                      disabled={voting}
                      className={`flex items-center space-x-1 px-2 py-1 rounded ${
                        comment.user_vote === 'upvote'
                          ? 'bg-orange-100 text-orange-600'
                          : 'hover:bg-gray-100'
                      }`}
                    >
                      <span>▲</span>
                      <span className="text-sm font-medium">{netVotes}</span>
                    </button>
                    <button
                      onClick={() => handleVote('downvote')}
                      disabled={voting}
                      className={`px-2 py-1 rounded ${
                        comment.user_vote === 'downvote'
                          ? 'bg-blue-100 text-blue-600'
                          : 'hover:bg-gray-100'
                      }`}
                    >
                      <span>▼</span>
                    </button>
                  </div>
                )}

                {/* Reply Button */}
                {allowReplies && !isMaxDepth && (
                  <button
                    onClick={() => setShowReplyForm(!showReplyForm)}
                    className="text-sm text-gray-600 hover:text-gray-900"
                  >
                    Reply {comment.reply_count > 0 && `(${comment.reply_count})`}
                  </button>
                )}

                {/* Delete Button (for comment owner) */}
                {/* TODO: Check if current user owns this comment */}
                {false && (
                  <button
                    onClick={() => onDelete(comment.id)}
                    className="text-sm text-red-600 hover:text-red-800"
                  >
                    Delete
                  </button>
                )}
              </div>
            )}

            {/* Reply Form */}
            {showReplyForm && !comment.is_deleted && (
              <div className="mt-4 pl-4 border-l-2 border-gray-200">
                <CommentForm
                  commentableType={commentableType}
                  commentableId={commentableId}
                  parentCommentId={comment.id}
                  onSuccess={() => {
                    setShowReplyForm(false);
                    onReply();
                  }}
                  onCancel={() => setShowReplyForm(false)}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Nested Replies */}
      {comment.replies && comment.replies.length > 0 && (
        <div className="space-y-2 mt-2">
          {comment.replies.map(reply => (
            <CommentCard
              key={reply.id}
              comment={reply}
              commentableType={commentableType}
              commentableId={commentableId}
              onVote={onVote}
              onRemoveVote={onRemoveVote}
              onDelete={onDelete}
              onReply={onReply}
              allowReplies={allowReplies}
              showVotes={showVotes}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Helper function to format time ago
function formatTimeAgo(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now - date) / 1000);

  const intervals = {
    year: 31536000,
    month: 2592000,
    week: 604800,
    day: 86400,
    hour: 3600,
    minute: 60
  };

  for (const [unit, secondsInUnit] of Object.entries(intervals)) {
    const interval = Math.floor(seconds / secondsInUnit);
    if (interval >= 1) {
      return `${interval} ${unit}${interval !== 1 ? 's' : ''} ago`;
    }
  }

  return 'just now';
}
