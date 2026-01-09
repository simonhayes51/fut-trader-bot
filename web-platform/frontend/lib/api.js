import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// API methods
export const api = {
  // Auth
  login: (data) => apiClient.post('/api/auth/login', data),
  logout: () => apiClient.post('/api/auth/logout'),

  // Traders
  getTraders: (params) => apiClient.get('/api/traders', { params }),
  getTrader: (id) => apiClient.get(`/api/traders/${id}`),
  getTraderSignals: (id, params) => apiClient.get(`/api/traders/${id}/signals`, { params }),
  getTraderStats: (id) => apiClient.get(`/api/traders/${id}/stats`),
  subscribe: (traderId) => apiClient.post(`/api/traders/${traderId}/subscribe`),
  unsubscribe: (traderId) => apiClient.delete(`/api/traders/${traderId}/subscribe`),

  // Signals
  getSignals: (params) => apiClient.get('/api/signals', { params }),
  getSignal: (id) => apiClient.get(`/api/signals/${id}`),

  // Reviews
  getReviews: (type, id, params) => apiClient.get(`/api/reviews/${type}/${id}`, { params }),
  createReview: (data) => apiClient.post('/api/reviews', data),
  voteReview: (id, voteType) => apiClient.post(`/api/reviews/${id}/vote`, { voteType }),
  removeReviewVote: (id) => apiClient.delete(`/api/reviews/${id}/vote`),

  // Comments
  getComments: (type, id, params) => apiClient.get(`/api/comments/${type}/${id}`, { params }),
  createComment: (data) => apiClient.post('/api/comments', data),
  voteComment: (id, voteType) => apiClient.post(`/api/comments/${id}/vote`, { voteType }),
  removeCommentVote: (id) => apiClient.delete(`/api/comments/${id}/vote`),

  // Community Content
  getCommunityContent: (params) => apiClient.get('/api/community', { params }),
  getCommunityPost: (id) => apiClient.get(`/api/community/${id}`),
  createCommunityPost: (data) => apiClient.post('/api/community', data),

  // Price Checker
  getPrice: (playerId) => apiClient.get(`/api/prices/${playerId}`),
};

export default apiClient;
