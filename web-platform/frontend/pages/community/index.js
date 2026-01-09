import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/layout/Layout';
import { api } from '../../lib/api';
import toast from 'react-hot-toast';

export default function CommunityPage() {
  const router = useRouter();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState('all');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadForm, setUploadForm] = useState({
    title: '',
    content: '',
    category: 'guide',
    thumbnail_url: ''
  });

  useEffect(() => {
    fetchPosts();
  }, [category]);

  const fetchPosts = async () => {
    try {
      setLoading(true);
      const params = category !== 'all' ? { category } : {};
      const response = await api.getCommunityContent(params);
      setPosts(response.data.posts || []);
    } catch (error) {
      console.error('Failed to fetch community posts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();

    if (!uploadForm.title || !uploadForm.content) {
      toast.error('Please fill in all required fields');
      return;
    }

    try {
      await api.createCommunityPost(uploadForm);
      toast.success('Post created successfully!');
      setShowUploadModal(false);
      setUploadForm({ title: '', content: '', category: 'guide', thumbnail_url: '' });
      fetchPosts();
    } catch (error) {
      toast.error(error.response?.data?.message || 'Failed to create post');
    }
  };

  return (
    <Layout title="Community - FUT Hub">
      {/* Hero Header */}
      <div className="bg-gradient-to-br from-purple-900 via-pink-900 to-purple-900 border-b border-purple-500/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-4xl md:text-5xl font-black text-white mb-2">
                💬 Community Guides
              </h1>
              <p className="text-purple-200 text-lg">
                Share your trading knowledge and learn from the best
              </p>
            </div>
            <button
              onClick={() => setShowUploadModal(true)}
              className="px-6 py-3 bg-gradient-to-r from-pink-500 to-purple-500 text-white rounded-xl font-bold hover:from-pink-600 hover:to-purple-600 transition-all shadow-lg hover:shadow-pink-500/50"
            >
              📝 Create Guide
            </button>
          </div>

          {/* Category Filter */}
          <div className="flex gap-3 overflow-x-auto pb-2">
            {['all', 'trading', 'sbc', 'market', 'guide'].map(cat => (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                className={`px-6 py-2 rounded-lg font-bold whitespace-nowrap transition-all ${
                  category === cat
                    ? 'bg-white text-purple-900 shadow-lg'
                    : 'bg-white/10 text-white hover:bg-white/20'
                }`}
              >
                {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Posts Grid */}
      <div className="min-h-screen bg-gradient-to-b from-black via-gray-900 to-black">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          {loading ? (
            <div className="text-center py-20">
              <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-purple-500"></div>
            </div>
          ) : posts.length === 0 ? (
            <div className="text-center py-20">
              <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-2xl p-12 border border-gray-700">
                <span className="text-7xl mb-6 block">📚</span>
                <h3 className="text-2xl font-bold text-white mb-4">
                  No Guides Yet
                </h3>
                <p className="text-gray-400 mb-8 max-w-md mx-auto">
                  Be the first to share your trading knowledge with the community
                </p>
                <button
                  onClick={() => setShowUploadModal(true)}
                  className="px-8 py-4 bg-gradient-to-r from-pink-500 to-purple-500 text-white rounded-xl font-bold hover:from-pink-600 hover:to-purple-600 transition-all shadow-lg hover:shadow-pink-500/50"
                >
                  Create First Guide
                </button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {posts.map(post => (
                <div
                  key={post.id}
                  onClick={() => router.push(`/community/${post.id}`)}
                  className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-purple-500/20 overflow-hidden hover:border-purple-500/40 transition-all shadow-xl hover:shadow-2xl hover:shadow-purple-500/20 cursor-pointer group"
                >
                  {post.thumbnail_url && (
                    <img
                      src={post.thumbnail_url}
                      alt={post.title}
                      className="w-full h-48 object-cover group-hover:scale-105 transition-transform"
                    />
                  )}
                  <div className="p-6">
                    <div className="flex items-center justify-between mb-3">
                      <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold ${
                        post.category === 'trading' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50' :
                        post.category === 'sbc' ? 'bg-green-500/20 text-green-400 border border-green-500/50' :
                        post.category === 'market' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50' :
                        'bg-pink-500/20 text-pink-400 border border-pink-500/50'
                      }`}>
                        {post.category?.toUpperCase()}
                      </span>
                      {post.is_featured && (
                        <span className="text-yellow-400 text-xl">⭐</span>
                      )}
                    </div>

                    <h3 className="text-xl font-bold text-white mb-3 line-clamp-2 group-hover:text-purple-400 transition-colors">
                      {post.title}
                    </h3>

                    <p className="text-gray-400 text-sm mb-4 line-clamp-3">
                      {post.content}
                    </p>

                    <div className="flex items-center justify-between text-sm text-gray-500 pt-4 border-t border-gray-800">
                      <span className="text-purple-400 font-medium">by {post.author_username}</span>
                      <div className="flex items-center gap-3">
                        <span>👍 {post.upvotes || 0}</span>
                        <span>💬 {post.comment_count || 0}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-br from-gray-900 to-black border border-purple-500/20 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-3xl font-black text-white">Create Community Guide</h2>
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="text-gray-400 hover:text-white text-2xl"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleUpload} className="space-y-6">
                <div>
                  <label className="block text-sm font-bold text-purple-400 mb-2">
                    Title *
                  </label>
                  <input
                    type="text"
                    value={uploadForm.title}
                    onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })}
                    placeholder="e.g., Ultimate Guide to Trading Icons"
                    className="w-full px-4 py-3 bg-black/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-bold text-purple-400 mb-2">
                    Category *
                  </label>
                  <select
                    value={uploadForm.category}
                    onChange={(e) => setUploadForm({ ...uploadForm, category: e.target.value })}
                    className="w-full px-4 py-3 bg-black/50 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="guide">General Guide</option>
                    <option value="trading">Trading Tips</option>
                    <option value="sbc">SBC Solutions</option>
                    <option value="market">Market Analysis</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-bold text-purple-400 mb-2">
                    Content *
                  </label>
                  <textarea
                    value={uploadForm.content}
                    onChange={(e) => setUploadForm({ ...uploadForm, content: e.target.value })}
                    placeholder="Share your knowledge, strategies, and tips..."
                    rows={10}
                    className="w-full px-4 py-3 bg-black/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 resize-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-bold text-purple-400 mb-2">
                    Thumbnail URL (optional)
                  </label>
                  <input
                    type="url"
                    value={uploadForm.thumbnail_url}
                    onChange={(e) => setUploadForm({ ...uploadForm, thumbnail_url: e.target.value })}
                    placeholder="https://..."
                    className="w-full px-4 py-3 bg-black/50 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div className="flex gap-4 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowUploadModal(false)}
                    className="flex-1 px-6 py-3 bg-gray-700 text-white rounded-lg font-bold hover:bg-gray-600 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 px-6 py-3 bg-gradient-to-r from-pink-500 to-purple-500 text-white rounded-lg font-bold hover:from-pink-600 hover:to-purple-600 transition-all shadow-lg hover:shadow-pink-500/50"
                  >
                    Publish Guide
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
