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

// ============================================================
// AUTH — unchanged
// ============================================================
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

// ============================================================
// CHUNK PREVIEW
// ============================================================

export const chunkPreviewAPI = {
  /**
   * Fetch a target chunk and its neighbors for the preview panel.
   *
   * @param {number} documentId
   * @param {number} chunkIndex
   * @param {number} [window=2]  - neighbors on each side
   */
  getChunks: (documentId, chunkIndex, window = 2) =>
    api.get('/api/rag/chunks', {
      params: {
        document_id: documentId,
        chunk_index: chunkIndex,
        window,
      },
    }),
};

// ============================================================
// CONVERSATIONS — unchanged
// ============================================================
export const conversationsAPI = {
  list: () => api.get('/api/conversations/'),
  create: (title = 'New Chat') => api.post('/api/conversations/', { title }),
  get: (id) => api.get('/api/conversations/' + id),
  update: (id, title) => api.patch('/api/conversations/' + id, { title }),
  delete: (id) => api.delete('/api/conversations/' + id),
};

// ============================================================
// CHAT (non-streaming) — unchanged
// ============================================================
export const chatAPI = {
  send: (message, conversationId = null, temperature = 0.7) =>
    api.post('/api/chat/', { message, conversation_id: conversationId, temperature }),
};

// ============================================================
// STREAM MESSAGE
// ============================================================
async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) throw new Error('No refresh token available');

  // Use plain axios (not the api instance) to avoid triggering the interceptor
  // again and causing an infinite refresh loop.
  const res = await axios.post(API_URL + '/api/auth/refresh', {
    refresh_token: refreshToken,
  });

  const { access_token, refresh_token: newRefreshToken } = res.data;
  localStorage.setItem('token', access_token);
  localStorage.setItem('refresh_token', newRefreshToken);
  api.defaults.headers.common['Authorization'] = 'Bearer ' + access_token;

  return access_token;
}

// ─── Helper: perform one fetch attempt to the stream endpoint ───────────────
async function fetchStream(token, message, conversationId, temperature, useRag) {
  return fetch('http://localhost:8000/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + token,
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      temperature,
      use_rag: useRag,
    }),
  });
}

// ─── streamMessage ───────────────────────────────────────────────────────────
// ONLY CHANGE from original: onDone now receives two extra args —
//   sources (array) and ragUsed (bool) — from the backend's final
//   SSE event. The rest of the function is identical.
// Auto-refreshes token on 401 and retries once before giving up.
export const streamMessage = async (
  message,
  conversationId,
  temperature = 0.7,
  useRag = true,
  onChunk,
  onDone
) => {
  let token = localStorage.getItem('token');
  let response = await fetchStream(token, message, conversationId, temperature, useRag);

  // ── Auto-refresh on 401 ──────────────────────────────────────────────────
  if (response.status === 401) {
    try {
      token = await refreshAccessToken();          // get fresh token
      response = await fetchStream(               // retry once
        token, message, conversationId, temperature, useRag
      );
    } catch {
      // Refresh failed (expired / invalid) → force re-login
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
      return;
    }
  }

  if (!response.ok) {
    throw new Error('HTTP error! status: ' + response.status);
  }

  // ── Stream the response ───────────────────────────────────────────────────
  const reader  = response.body.getReader();
  const decoder = new TextDecoder();

  let streamDone = false;

while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n');

    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (!data) continue;

            if (data === '[END_OF_MESSAGE]') { streamDone = true; break; }

            try {
                const parsed = JSON.parse(data);
                if (parsed.content) onChunk(parsed.content);
                if (parsed.done) onDone(parsed.conversation_id, parsed.message_id, parsed.sources ?? [], parsed.rag_used ?? false, parsed.conversation_title ?? null);
                if (parsed.error) throw new Error(parsed.error);
            } catch {
                // skip malformed chunks
            }
        }
    }
    if (streamDone) break;
}
};

export const searchAPI = {
  /**
   * Semantic search across the user's documents.
   *
   * @param {string}  query
   * @param {Object}  [opts]
   * @param {number}  [opts.topK]           - max results (default: backend's SEARCH_TOP_K=8)
   * @param {string}  [opts.topic]          - optional TopicEnum filter
   * @param {number}  [opts.scoreThreshold] - optional override
   */
  search: (query, { topK, topic, scoreThreshold } = {}) => {
    const params = new URLSearchParams({ q: query });
    if (topK)           params.append('top_k',           topK);
    if (topic)          params.append('topic',           topic);
    if (scoreThreshold) params.append('score_threshold', scoreThreshold);
    return api.get(`/api/rag/search?${params.toString()}`);
  },
};

// ============================================================
// DOCUMENTS — NEW
// ============================================================

// Exported so DocumentUpload and DocumentLibrary dropdowns
// always stay in sync with a single source of truth.
export const DOCUMENT_TOPICS = [
  { value: 'python',           label: 'Python' },
  { value: 'java',             label: 'Java' },
  { value: 'javascript',       label: 'JavaScript' },
  { value: 'typescript',       label: 'TypeScript' },
  { value: 'cpp',              label: 'C++' },
  { value: 'csharp',           label: 'C#' },
  { value: 'go',               label: 'Go' },
  { value: 'rust',             label: 'Rust' },
  { value: 'php',              label: 'PHP' },
  { value: 'ruby',             label: 'Ruby' },
  { value: 'swift',            label: 'Swift' },
  { value: 'kotlin',           label: 'Kotlin' },
  { value: 'sql',              label: 'SQL' },
  { value: 'web',              label: 'Web (HTML/CSS)' },
  { value: 'data-science',     label: 'Data Science' },
  { value: 'machine-learning', label: 'Machine Learning' },
  { value: 'algorithms',       label: 'Algorithms & DS' },
  { value: 'system-design',    label: 'System Design' },
];

export const DOCUMENT_STATUSES = [
  { value: 'processing', label: 'Processing' },
  { value: 'completed',  label: 'Completed' },
  { value: 'failed',     label: 'Failed' },
];

export const documentsAPI = {
  /**
   * Upload a PDF via multipart/form-data.
   * axios sets Content-Type automatically when given FormData.
   *
   * @param {File}     file
   * @param {string}   topic
   * @param {string}   [title='']
   * @param {boolean}  [isPublic=false]
   * @param {Function} [onProgress] - (percent: number) => void
   */
  upload: (file, topic, title = '', isPublic = false, onProgress = null) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('topic', topic);
    if (title) formData.append('title', title);
    formData.append('is_public', isPublic ? '1' : '0');

    return api.post('/api/rag/upload', formData, {
      headers: { 'Content-Type': undefined },
      onUploadProgress: onProgress
        ? (evt) => {
            const percent = evt.total
              ? Math.round((evt.loaded * 100) / evt.total)
              : 0;
            onProgress(percent);
          }
        : undefined,
    });
  },

  list: ({ topic = '', status = '', page = 1, page_size = 12 } = {}) => {
    const params = { page, page_size };
    if (topic)  params.topic  = topic;
    if (status) params.status = status;
    return api.get('/api/rag/documents', { params });
  },

  get:    (id) => api.get(`/api/rag/documents/${id}`),
  delete: (id) => api.delete(`/api/rag/documents/${id}`),
};

export default api;