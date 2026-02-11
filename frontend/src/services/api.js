import axios from 'axios';

const API_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers['Authorization'] = 'Bearer ' + token;
          return api(originalRequest);
        }).catch(err => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');

      if (!refreshToken) {
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(
          API_URL + '/api/auth/refresh',
          { refresh_token: refreshToken }
        );

        const { access_token, refresh_token: newRefreshToken } = response.data;

        localStorage.setItem('token', access_token);
        localStorage.setItem('refresh_token', newRefreshToken);

        api.defaults.headers.common['Authorization'] = 'Bearer ' + access_token;
        processQueue(null, access_token);

        originalRequest.headers['Authorization'] = 'Bearer ' + access_token;
        return api(originalRequest);

      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export const authAPI = {
  register: (email, username, password) =>
    api.post('/api/auth/register', { email, username, password }),

  login: (email, password) =>
    api.post('/api/auth/login',
      new URLSearchParams({ username: email, password }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    ),

  getMe: () => api.get('/api/auth/me'),

  logout: () => api.post('/api/auth/logout'),
};

export const conversationsAPI = {
  list: () => api.get('/api/conversations/'),
  create: (title = 'New Chat') => api.post('/api/conversations/', { title }),
  get: (id) => api.get('/api/conversations/' + id),
  update: (id, title) => api.patch('/api/conversations/' + id, { title }),
  delete: (id) => api.delete('/api/conversations/' + id),
};

export const chatAPI = {
  send: (message, conversationId = null, temperature = 0.7) =>
    api.post('/api/chat/', { message, conversation_id: conversationId, temperature }),
};

export const streamMessage = async (message, conversationId, temperature = 0.7, onChunk, onDone) => {
  const token = localStorage.getItem('token');

  const response = await fetch('http://localhost:8000/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + token,
    },
    body: JSON.stringify({ message, conversation_id: conversationId, temperature }),
  });

  if (!response.ok) {
    throw new Error('HTTP error! status: ' + response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (!data) continue;
        try {
          const parsed = JSON.parse(data);
          if (parsed.content) onChunk(parsed.content);
          if (parsed.done) onDone(parsed.conversation_id, parsed.message_id);
          if (parsed.error) throw new Error(parsed.error);
        } catch (e) {
          // Skip malformed JSON
        }
      }
    }
  }
};

export default api;