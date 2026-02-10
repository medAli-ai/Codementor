import axios from 'axios';

// Base URL for our backend
const API_URL = 'http://localhost:8000';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Automatically add JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Automatically handle 401 (token expired)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired - clear storage and redirect to login
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ============ Auth API ============

export const authAPI = {
  register: (email, username, password) =>
    api.post('/api/auth/register', { email, username, password }),

  login: (email, password) =>
    api.post('/api/auth/login',
      // OAuth2 requires form data format
      new URLSearchParams({ username: email, password }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    ),

  getMe: () =>
    api.get('/api/auth/me'),
};

// ============ Conversations API ============

export const conversationsAPI = {
  list: () =>
    api.get('/api/conversations/'),

  create: (title = 'New Chat') =>
    api.post('/api/conversations/', { title }),

  get: (id) =>
    api.get(`/api/conversations/${id}`),

  update: (id, title) =>
    api.patch(`/api/conversations/${id}`, { title }),

  delete: (id) =>
    api.delete(`/api/conversations/${id}`),
};

// ============ Chat API ============

export const chatAPI = {
  send: (message, conversationId = null, temperature = 0.7) =>
    api.post('/api/chat/', {
      message,
      conversation_id: conversationId,
      temperature,
    }),
};

export default api;