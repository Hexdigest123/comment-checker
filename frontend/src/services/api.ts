import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import type { ApiError, CommentSearchResult, GraphData, AIChatResponse, ImportStatus } from '../types';

const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors and refresh tokens
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle 401 Unauthorized - try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
          throw new Error('No refresh token');
        }

        const response = await axios.post(
          `${import.meta.env.PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/auth/refresh`,
          { refresh_token: refreshToken },
          { headers: { 'Content-Type': 'application/json' } }
        );

        const { access_token } = response.data;
        localStorage.setItem('access_token', access_token);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }

        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed - logout user
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    // Transform error response
    const apiError: ApiError = {
      detail: error.response?.data?.detail || error.message || 'An unexpected error occurred',
      status_code: error.response?.status || 500,
    };

    return Promise.reject(apiError);
  }
);

// Auth API
export const authApi = {
  login: (data: { username: string; password: string }) =>
    api.post<{ access_token: string; token_type: string; user: unknown }>('/auth/login', data),

  refresh: (refreshToken: string) =>
    api.post<{ access_token: string; token_type: string }>('/auth/refresh', { refresh_token: refreshToken }),

  logout: () => api.post('/auth/logout'),

  me: () => api.get<{ id: number; username: string; full_name: string | null; is_active: boolean; is_admin: boolean }>('/users/me'),
};

// Comment API
export const commentApi = {
  list: (params?: { page?: number; page_size?: number; search?: string; status?: string; sort_by?: string; sort_order?: string }) =>
    api.get('/comments', { params }),

  get: (id: string) => api.get(`/comments/${id}`),

  create: (data: unknown) => api.post('/comments', data),

  update: (id: string, data: unknown) => api.put(`/comments/${id}`, data),

  delete: (id: string) => api.delete(`/comments/${id}`),

  uploadCSV: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/comments/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  classify: (id: string) => api.post(`/classifications/${id}/classify`),

  reclassify: (id: string) => api.post(`/classifications/${id}/classify`),

  semanticSearch: (query: string, limit = 10) =>
    api.get<CommentSearchResult[]>('/comments/search/semantic', {
      params: { query, limit },
    }),
};

// Classification API
export const classificationApi = {
  list: (params?: { page?: number; page_size?: number; comment_id?: string; backend?: string; category?: string }) =>
    api.get('/classifications', { params }),

  get: (id: string) => api.get(`/classifications/${id}`),

  stats: () => api.get('/classifications/stats'),
};

// Cluster / graph API
export const clusterApi = {
  graph: () => api.get<GraphData>('/clusters/graph'),

  clusterGraph: (clusterId: string) => api.get<GraphData>(`/clusters/${clusterId}/graph`),

  list: (params?: Record<string, string | number>) => api.get('/clusters', { params }),
};

// AI assistant API (agentic workflow — tools are always enabled)
export const aiApi = {
  chat: (message: string, sessionId?: string | null) =>
    api.post<AIChatResponse>('/ai/chat', {
      message,
      session_id: sessionId,
    }),

  conversations: (sessionId?: string) =>
    api.get('/ai/conversations', { params: sessionId ? { session_id: sessionId } : {} }),

  sessions: () => api.get<string[]>('/ai/sessions'),

  stats: () => api.get('/ai/stats'),

  deleteSession: (sessionId: string) => api.delete(`/ai/sessions/${sessionId}`),
};

// Import API (ExportComments.com)
export const importApi = {
  status: () => api.get<ImportStatus>('/import/exportcomments/status'),

  fromUrl: (data: {
    url: string;
    context?: string;
    include_replies?: boolean;
    max_comments?: number;
  }) => api.post('/import/exportcomments', data),
};

export default api;
